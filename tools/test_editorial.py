import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import article_policy as policy
import editorial


class ArticlePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'content/posts').mkdir(parents=True)
        (self.root / 'tools').mkdir()
        (self.root / 'tools/editorial-config.json').write_text('{"posts_per_seven_days": 3}')
        self.now = dt.datetime(2026, 11, 15, tzinfo=dt.timezone.utc)
        self.info = {'title': 'A useful article', 'date': self.now.isoformat(),
                     'sources': [{'url': 'https://example.com/a'}, {'url': 'https://example.com/b'}]}
        self.pr = {'state': 'open', 'draft': False, 'user': {'login': policy.OWNER},
                   'base': {'ref': 'main'}, 'head': {'repo': {'full_name': policy.REPO}, 'ref': 'auto-post/abc'},
                   'labels': [{'name': policy.LABEL}]}
        self.files = [{'status': 'added', 'filename': 'content/posts/new-post.html'}]
        self.tree = [{'path': self.files[0]['filename'], 'type': 'blob', 'mode': '100644'}]

    def article(self, body='<p>Useful <a href="https://example.com">source</a>.</p>'):
        return '<!--' + json.dumps(self.info) + '-->\n' + body

    def validate(self, body=None):
        return policy.validate(self.pr, self.files, self.tree, self.article() if body is None else self.article(body), self.root, self.now)

    def test_new_owner_article(self):
        self.assertEqual(self.validate(), 'content/posts/new-post.html')

    def test_untrusted_identity(self):
        self.pr['user']['login'] = 'stranger'
        with self.assertRaises(ValueError): self.validate()

    def test_fork(self):
        self.pr['head']['repo']['full_name'] = 'stranger/site'
        with self.assertRaises(ValueError): self.validate()

    def test_modified_extra_or_executable_files(self):
        self.files[0]['status'] = 'modified'
        with self.assertRaises(ValueError): self.validate()
        self.files[0]['status'] = 'added'
        self.files.append({'filename': '.github/workflows/pages.yml', 'status': 'modified'})
        with self.assertRaises(ValueError): self.validate()
        self.files.pop()
        self.tree[0]['mode'] = '120000'
        with self.assertRaises(ValueError): self.validate()

    def test_active_content_and_metadata_rejected(self):
        for body in ['<script>alert(1)</script>', '<p onclick="alert(1)">x</p>',
                     '<a href="jav&#x61;script:alert(1)">x</a>', '<iframe src="https://example.com"></iframe>',
                     '<p style="position:fixed">x</p>', '{{video:abcdefghijk|Title}}']:
            with self.subTest(body=body), self.assertRaises(ValueError): self.validate(body)
        self.info['title'] = '</script><script>alert(1)</script>'
        with self.assertRaises(ValueError): self.validate()

    def test_stale_future_and_naive_dates(self):
        for date in [self.now - dt.timedelta(days=3), self.now + dt.timedelta(hours=1), self.now.replace(tzinfo=None)]:
            self.info['date'] = date.isoformat()
            with self.subTest(date=date), self.assertRaises(ValueError): self.validate()

    def test_quota_boundary_and_next_slot(self):
        for i, days in enumerate([8, 6, 5, 1]):
            self.info['date'] = (self.now - dt.timedelta(days=days)).isoformat()
            (self.root / f'content/posts/old-{i}.html').write_text(self.article())
        budget = policy.quota(self.root, self.now, 3)
        self.assertEqual(budget['used'], 3)
        self.assertEqual(budget['next_slot_at'], (self.now + dt.timedelta(days=1)).isoformat())
        self.info['date'] = self.now.isoformat()
        with self.assertRaisesRegex(ValueError, 'quota full'): self.validate()
        self.assertEqual(policy.quota(self.root, self.now + dt.timedelta(days=1), 3)['available'], 1)


class QueueTests(unittest.TestCase):
    def test_feed_parsing(self):
        self.assertEqual(editorial.feed_entries(b'<rss><channel><item><title>A title</title><link>https://example.com</link></item></channel></rss>')[0]['title'], 'A title')
        self.assertEqual(editorial.feed_entries(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom</title><link href="https://example.com"/></entry></feed>')[0]['url'], 'https://example.com')
        self.assertEqual(editorial.feed_entries(b'<rss><item><title>x</title><link>javascript:alert(1)</link></item></rss>'), [])

    def test_stable_request_and_queue_conflict(self):
        self.assertEqual(editorial.request_branch('wa:123'), editorial.request_branch('wa:123'))
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), contextlib.redirect_stdout(io.StringIO()):
            editorial.queue_request('Owner topic', 'wa:123')
            editorial.queue_request('Owner topic', 'wa:123')
            with self.assertRaises(ValueError): editorial.queue_request('Changed topic', 'wa:123')
            self.assertEqual(len(editorial.read(Path(temp) / 'owner-queue.json', {})), 1)

    def test_existing_request_does_not_push_or_create(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'existing_pr', return_value={'number': 99, 'url': 'https://github.com/pr/99', 'state': 'MERGED', 'isDraft': False}), patch.object(editorial, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            editorial.submit(Path('not-needed.html'), 'already-published', Path('not-needed.md'))
            run.assert_not_called()

    def test_live_receipt_requires_body(self):
        self.assertFalse(editorial.published_matches('<h1>Title</h1>', 'Title', '<p>Content</p>'))
        self.assertTrue(editorial.published_matches('<h1>A &amp; B</h1><p>Content</p>', 'A & B', '<p>Content</p>'))


if __name__ == '__main__':
    unittest.main()
