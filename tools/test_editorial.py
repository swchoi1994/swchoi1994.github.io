import contextlib
import datetime as dt
import io
import json
import os
import subprocess
import shutil
import sys
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
                     '<p style="position:fixed">x</p>', '{{video:abcdefghijk|Title}}',
                     '<img src=https://x.invalid/ onerror=alert(1)', '<a href="javascript:alert(1)"']:
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

    def test_fork_cannot_overwrite_owner_commit_status(self):
        self.pr.update(number=7)
        self.pr['head'].update(sha='shared-sha')
        self.pr['head']['repo']['full_name'] = 'outsider/fork'
        self.pr['user']['login'] = 'outsider'
        event = self.root / 'event.json'
        event.write_text(json.dumps({'pull_request': self.pr}))
        with patch.object(sys, 'argv', ['policy', '--event', str(event), '--report-status']), patch.object(policy, 'api', return_value=self.pr), patch.object(policy, 'report_status') as report, contextlib.redirect_stdout(io.StringIO()):
            policy.main()
            report.assert_not_called()

    def test_manual_pr_cannot_clear_shared_automatic_failure(self):
        self.pr.update(number=7)
        self.pr['head'].update(sha='shared-sha', ref='manual/copy')
        self.pr['labels'] = []
        peer = json.loads(json.dumps(self.pr))
        peer['number'] = 8
        peer['head']['ref'] = 'auto-post/pending'
        event = self.root / 'event.json'
        event.write_text(json.dumps({'pull_request': self.pr}))
        with patch.object(sys, 'argv', ['policy', '--event', str(event), '--report-status']), patch.object(policy, 'api', return_value=self.pr), patch.object(policy, 'trusted_automatic_peers', return_value=[peer['number']]), patch.object(policy, 'inspect_pr', side_effect=ValueError('Automatic PR held')), patch.object(policy, 'report_status') as report:
            with self.assertRaisesRegex(ValueError, 'held'): policy.main()
            self.assertEqual([c.args[1] for c in report.call_args_list], ['pending', 'failure'])

    def test_lookup_failure_invalidates_prior_approval(self):
        self.pr.update(number=7)
        self.pr['head'].update(sha='shared-sha')
        self.pr['labels'] = []  # Owner removed auto-publish while other CI was pending.
        event = self.root / 'event.json'
        event.write_text(json.dumps({'pull_request': self.pr}))
        with patch.object(sys, 'argv', ['policy', '--event', str(event), '--report-status']), patch.object(policy, 'api', side_effect=OSError('GitHub lookup unavailable')), patch.object(policy, 'report_status') as report:
            with self.assertRaises(OSError): policy.main()
            self.assertEqual([c.args[1] for c in report.call_args_list], ['pending', 'failure'])

    def test_peer_lookup_paginates_authoritative_associations_before_owner_limit(self):
        owner = {'number': 7, 'user': {'login': policy.OWNER}, 'state': 'open', 'head': {'sha': 'same', 'ref': 'auto-post/post', 'repo': {'full_name': policy.REPO}}, 'labels': []}
        foreign = {'number': 8, 'user': {'login': 'outsider'}, 'state': 'open'}
        pages = [[foreign] * 1000, [foreign, owner]]
        with patch.object(policy.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout=json.dumps(pages))) as run:
            self.assertEqual(policy.trusted_automatic_peers('same'), [7])
            args = run.call_args.args[0]
            self.assertEqual(args[:4], ['gh', 'api', '--paginate', '--slurp'])
            self.assertIn('/commits/same/pulls?', args[-1])


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

    def test_submission_retry_respects_native_stop(self):
        pr = {'number': 7, 'url': 'https://github.com/pr/7', 'state': 'OPEN', 'isDraft': False, 'autoMergeRequest': None}
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'existing_pr', return_value=pr), patch.object(editorial, 'enqueue') as enqueue, contextlib.redirect_stdout(io.StringIO()):
            editorial.submit(Path('not-needed.html'), 'wa:stopped', Path('not-needed.md'))
            enqueue.assert_not_called()
            self.assertEqual(editorial.read(editorial.receipt_path(editorial.request_branch('wa:stopped')), {})['status'], 'paused')

    def test_live_receipt_requires_body(self):
        self.assertFalse(editorial.published_matches('<h1>Title</h1>', 'Title', '<p>Content</p>'))
        self.assertTrue(editorial.published_matches('<h1>A &amp; B</h1><p>Content</p>', 'A & B', '<p>Content</p>'))

    def test_table_receipt_matches_rendered_page(self):
        import publish
        body = '<p>Comparison</p><table><tr><td>Evidence</td></tr></table>'
        document = '<h1>Title</h1>' + publish.scrollable_tables(body)
        self.assertTrue(editorial.published_matches(document, 'Title', body))
        self.assertFalse(editorial.published_matches(document.replace('Evidence', 'Old data'), 'Title', body))

    def test_receipts_match_all_eligible_generated_native_articles(self):
        import publish
        posts = publish.load_articles()
        for post in posts:
            if not post.get('native') or '{{video:' in post['native']['body']:
                continue  # Embedded media is outside the automatic article policy.
            with self.subTest(slug=post['slug']), patch.object(publish, 'write') as write:
                publish.article(post, posts)
                self.assertTrue(editorial.published_matches(write.call_args.args[1], post['title'], post['native']['body']))

    def test_owner_queue_does_not_require_network_or_clean_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            tools = state / 'runtime/tools'
            tools.mkdir(parents=True)
            for name in ['editorial.py', 'article_policy.py']:
                shutil.copy(policy.ROOT / 'tools' / name, tools / name)
            (state / 'runtime/uncommitted.txt').write_text('Preserve this edit')
            fakebin = state / 'bin'
            fakebin.mkdir()
            git = fakebin / 'git'
            git.write_text('#!/bin/sh\nexit 81\n')
            git.chmod(0o755)
            result = subprocess.run(['bash', str(policy.ROOT / 'tools/editorial-run.sh'), 'queue', '--request-id', 'wa:offline', '--topic', 'Owner brief'], env={**os.environ, 'JOURNAL_EDITORIAL_STATE': str(state), 'PATH': str(fakebin) + os.pathsep + os.environ['PATH']}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(editorial.read(state / 'owner-queue.json', {})), 1)

    def test_existing_pr_ignores_foreign_same_named_branches(self):
        foreign = {'number': 1, 'user': {'login': 'outsider'}}
        own = {'number': 2, 'user': {'login': policy.OWNER}, 'base': {'ref': 'main'}, 'head': {'ref': 'auto-post/shared', 'repo': {'full_name': policy.REPO}}, 'html_url': 'https://github.com/pr/2', 'state': 'open', 'draft': False, 'auto_merge': None}
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'run', return_value=json.dumps([[foreign] * 100, [own]])) as run:
            self.assertEqual(editorial.existing_pr('auto-post/shared')['number'], 2)
            args = run.call_args.args
            self.assertEqual(args[:4], ('gh', 'api', '--paginate', '--slurp'))
            self.assertIn('head=swchoi1994%3Aauto-post%2Fshared', args[-1])

    def test_retargeted_orphan_request_is_held_not_replaced(self):
        pr = {'number': 7, 'user': {'login': policy.OWNER}, 'base': {'ref': 'archive'}, 'head': {'ref': 'auto-post/shared', 'repo': {'full_name': policy.REPO}}}
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'run', return_value=json.dumps([[pr]])) as run:
            with self.assertRaisesRegex(ValueError, 'another base'):
                editorial.existing_pr('auto-post/shared')
            self.assertNotIn('base=', run.call_args.args[-1])

    def test_saved_closed_request_cannot_be_replaced_by_inventory_omission(self):
        branch = editorial.request_branch('wa:cancelled')
        pr = {'number': 7, 'user': {'login': policy.OWNER}, 'base': {'ref': 'main'}, 'head': {'ref': branch, 'repo': {'full_name': policy.REPO}}, 'html_url': 'https://github.com/pr/7', 'state': 'closed', 'draft': False, 'auto_merge': None}
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'api', return_value=pr) as api, patch.object(editorial, 'run') as run, patch.object(editorial, 'enqueue') as enqueue, contextlib.redirect_stdout(io.StringIO()):
            editorial.save(editorial.receipt_path(branch), {'pr': 7, 'branch': branch, 'status': 'closed'})
            editorial.submit(Path('not-needed.html'), 'wa:cancelled', Path('not-needed.md'))
            api.assert_called_once_with('pulls/7')
            run.assert_not_called()
            enqueue.assert_not_called()

    def test_saved_request_lookup_failure_never_falls_back_to_creation(self):
        branch = editorial.request_branch('wa:uncertain')
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'api', side_effect=OSError('Unavailable')), patch.object(editorial, 'run') as run:
            editorial.save(editorial.receipt_path(branch), {'pr': 7, 'branch': branch})
            with self.assertRaises(OSError): editorial.existing_pr(branch)
            run.assert_not_called()

    def test_hold_keeps_later_owner_requests_moving_and_can_resume(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'quota', return_value={'available': 1}):
            with contextlib.redirect_stdout(io.StringIO()):
                editorial.queue_request('Unverifiable claim', 'wa:1')
                editorial.queue_request('Useful topic', 'wa:2')
                editorial.decision('wa:1', 'Primary source unavailable')
            output = io.StringIO()
            with contextlib.redirect_stdout(output): editorial.next_topic()
            self.assertEqual(json.loads(output.getvalue())['next']['request_id'], 'wa:2')
            with contextlib.redirect_stdout(io.StringIO()): editorial.decision('wa:1')
            output = io.StringIO()
            with contextlib.redirect_stdout(output): editorial.next_topic()
            self.assertEqual(json.loads(output.getvalue())['next']['request_id'], 'wa:1')

    def test_command_failures_retain_diagnostics(self):
        error = subprocess.CalledProcessError(1, ['test'], stderr='Title exceeds 60 characters')
        output = io.StringIO()
        with patch.object(editorial.subprocess, 'run', side_effect=error), contextlib.redirect_stderr(output), self.assertRaises(subprocess.CalledProcessError):
            editorial.run('test')
        self.assertIn('Title exceeds', output.getvalue())

    def test_branch_update_uses_api_head_lease(self):
        row = {'number': 7, 'headRefName': 'auto-post/abc', 'isDraft': False, 'isCrossRepository': False, 'author': {'login': policy.OWNER}, 'autoMergeRequest': {'enabledAt': '2026-11-15'}}
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'run', side_effect=[json.dumps([row]), '']) as run, patch.object(editorial, 'inspect_pr', return_value={'head_sha': 'expected'}), patch.object(editorial, 'api', return_value={'mergeable_state': 'behind'}), patch.object(editorial, 'enqueue') as enqueue, contextlib.redirect_stdout(io.StringIO()):
            editorial.reconcile()
            self.assertEqual(run.call_args.args, ('gh', 'api', '--method', 'PUT', f'repos/{policy.REPO}/pulls/7/update-branch', '-f', 'expected_head_sha=expected'))
            enqueue.assert_not_called()

    def test_reconcile_does_not_reverse_a_stop(self):
        row = {'number': 7, 'headRefName': 'auto-post/abc', 'isDraft': False, 'isCrossRepository': False, 'author': {'login': policy.OWNER}, 'autoMergeRequest': None}
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'run', return_value=json.dumps([row])) as run, patch.object(editorial, 'inspect_pr') as inspect, patch.object(editorial, 'enqueue') as enqueue, contextlib.redirect_stdout(io.StringIO()):
            editorial.reconcile()
            enqueue.assert_not_called()
            inspect.assert_not_called()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(editorial.read(editorial.receipt_path('auto-post/abc'), {})['status'], 'paused')
            output = io.StringIO()
            with patch.object(editorial, 'quota', return_value={'available': 1}), contextlib.redirect_stdout(output):
                editorial.next_topic()
            state = json.loads(output.getvalue())
            self.assertEqual(state['paused_prs'], [7])
            self.assertEqual(state['pending_prs'], [])

    def test_receipt_check_releases_stopped_request_even_after_label_removal(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'api', return_value={'state': 'open', 'merged_at': None, 'auto_merge': None}), contextlib.redirect_stdout(io.StringIO()):
            path = editorial.receipt_path('auto-post/abc')
            editorial.save(path, {'pr': 7, 'branch': 'auto-post/abc', 'status': 'auto_merge_requested'})
            editorial.receipts()
            self.assertEqual(editorial.read(path, {})['status'], 'paused')

    def test_explicit_owner_resume_enrolls_once(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(editorial, 'STATE', Path(temp)), patch.object(editorial, 'enqueue', return_value={'head_sha': 'head', 'path': 'content/posts/post.html'}) as enqueue, patch.object(editorial, 'api', return_value={'head': {'ref': 'auto-post/abc'}, 'html_url': 'https://github.com/pr/7'}), contextlib.redirect_stdout(io.StringIO()):
            editorial.resume_pr(7)
            enqueue.assert_called_once_with(7)
            self.assertEqual(editorial.read(editorial.receipt_path('auto-post/abc'), {})['status'], 'auto_merge_requested')


if __name__ == '__main__':
    unittest.main()
