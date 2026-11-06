"""Publication acceptance checks: discoverability, preserved content and affiliate boundaries."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import urljoin, urlsplit, unquote, parse_qs
import xml.etree.ElementTree as ET

import publish
from affiliates import apply_affiliates, load_affiliates


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.links = []
        self.ids = set()
        self.h1 = 0
        self.canonicals = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'h1':
            self.h1 += 1
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs['href'])
        for attr in ('href', 'src'):
            if attr in attrs:
                self.links.append(attrs[attr])


class PublicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (publish.OUT / 'index.html').exists():
            publish.build()
        cls.posts = publish.load_articles()

    def test_every_page_has_one_heading_canonical_and_valid_local_links(self):
        broken = []
        for path in publish.OUT.rglob('index.html'):
            route = '/' + str(path.parent.relative_to(publish.OUT)).strip('.')
            route = route.rstrip('/') + '/'
            doc = Document(path.read_text())
            self.assertEqual(doc.h1, 1, route)
            self.assertEqual(doc.canonicals, [publish.SITE + route], route)
            for href in doc.links:
                url = urlsplit(urljoin(publish.SITE + route, href))
                if url.netloc != urlsplit(publish.SITE).netloc or url.scheme not in ('https', 'http'):
                    continue
                target = publish.OUT / unquote(url.path).lstrip('/')
                if target.is_dir():
                    target = target / 'index.html'
                if not target.exists():
                    broken.append((route, href))
                elif url.fragment and target.suffix == '.html':
                    # Legacy fragments are redirected by the homepage compatibility script.
                    legacy = url.path == '/' and url.fragment in ('work', 'experience', 'research', 'education', 'contact')
                    if not legacy and unquote(url.fragment) not in Document(target.read_text()).ids:
                        broken.append((route, href))
        self.assertEqual(broken, [])

    def test_every_page_has_one_google_analytics_tag(self):
        wrong = []
        for path in publish.OUT.rglob('*.html'):
            if path.relative_to(publish.OUT).parts[0] == 'openclaw-setup':
                continue
            source = path.read_text()
            head = source.split('</head>')[0]
            if head.count('googletagmanager.com/gtag/js?id=G-BLKN59SYTQ') != 1 or head.count("gtag('config','G-BLKN59SYTQ')") != 1 or source.count('googletagmanager.com') != 1:
                wrong.append(str(path.relative_to(publish.OUT)))
        self.assertEqual(wrong, [])

    def test_home_features_the_owners_fifteen_ai_picks(self):
        home = (publish.OUT / 'index.html').read_text()
        wanted = [slug for _, ids in publish.AI_PICKS for slug in ids]
        self.assertEqual(len(wanted), 15)
        self.assertEqual(len(set(wanted)), 15)
        for slug in wanted:
            self.assertIn(f'href="/blog/posts/{slug}/"', home, slug)
        self.assertEqual([m for m in re.findall(r'<h3 class="pick-heading">(.*?)</h3>', home)], [name for name, _ in publish.AI_PICKS])

    def test_articles_keep_sources_dates_and_have_relevant_navigation(self):
        for post in self.posts:
            source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
            schemas = [json.loads(m[1]) for m in publish.LD.finditer(source)]
            data = next(s for s in schemas if s.get('@type') == 'BlogPosting')
            self.assertEqual(data['datePublished'], post['schema']['datePublished'])
            self.assertEqual(data.get('citation'), post['schema'].get('citation'))
            self.assertEqual(data['headline'], post['title'])
            self.assertIn(f'/topics/{post["topic"]}/', source)
            self.assertIn('At a glance', source)
            self.assertIn('A useful next read', source)
            self.assertIn(f'https://blog.naver.com/swchoi1994/{post["slug"].split("-")[1]}', source)
            self.assertIn('Editorial policy', source)

    def test_all_articles_are_in_search_archive_and_sitemap(self):
        index = json.loads((publish.OUT / 'blog/search-index.json').read_text())
        self.assertEqual({p['url'] for p in index}, {p['url'] for p in self.posts})
        archive = (publish.OUT / 'blog/index.html').read_text()
        archive += ''.join(p.read_text() for p in (publish.OUT / 'blog/page').glob('*/index.html'))
        for post in self.posts:
            self.assertIn(post['url'], archive)
        sitemap = ET.parse(publish.OUT / 'sitemap.xml')
        urls = {node.text for node in sitemap.findall('.//{*}loc')}
        self.assertEqual(len(urls), len(list(publish.OUT.rglob('index.html'))))
        self.assertTrue({publish.SITE + p['url'] for p in self.posts} <= urls)
        ET.parse(publish.OUT / 'blog/feed.xml')
        self.assertIn('pub-5340843733211852', (publish.OUT / 'ads.txt').read_text())

    def test_localization_preserves_original_and_unknown_destinations(self):
        source = '<a href="https://blog.naver.com/swchoi1994/111">current</a><a href="https://blog.naver.com/swchoi1994/222">next</a><a href="https://blog.naver.com/swchoi1994/333">missing</a>'
        output = publish.localize_links(source, 'naver-111', {'naver-111', 'naver-222'})
        self.assertIn('href="/blog/posts/naver-222/"', output)
        self.assertIn('https://blog.naver.com/swchoi1994/111', output)
        self.assertIn('https://blog.naver.com/swchoi1994/333', output)

    def test_classifier_keeps_reader_intent(self):
        for title, topic in [('Windows Update fails', 'windows'), ('Gmail filters', 'google-tools'), ('Excel SUMIFS #VALUE! error', 'office-documents'), ('Cloud sync and backup', 'privacy-backup'), ('Claude Skills', 'ai-automation')]:
            self.assertEqual(publish.topic_for(title), topic)


class AffiliateTest(unittest.TestCase):
    config = {'marketplace': 'amazon.com', 'tracking_id': 'example-20', 'placements': {}}

    def test_tagging_disclosure_and_host_boundary(self):
        source = '<header class="reading-header"></header><a href="https://www.amazon.com/dp/B012345678/?tag=old-20&amp;th=1" rel="external">Product</a><a href="https://amazon.com.evil.test/dp/B012345678/">Other</a><a href="https://amazon.com@evil.test/dp/B012345678/">Other</a><a href="https://www.amazon.co.uk/dp/B012345678/">UK</a>'
        output = apply_affiliates(source, 'example', self.config)
        doc = Document(output)
        query = parse_qs(urlsplit(doc.links[0]).query)
        self.assertEqual(query, {'tag': ['example-20'], 'th': ['1']})
        self.assertIn('rel="external nofollow noopener sponsored"', output)
        self.assertEqual(output.count('As an Amazon Associate'), 1)
        self.assertNotIn('tag=example-20', doc.links[1])
        self.assertNotIn('tag=example-20', doc.links[2])
        self.assertNotIn('tag=example-20', doc.links[3])
        self.assertEqual(apply_affiliates(source, 'example', None), source)

    def test_selected_product_placement_and_escaping(self):
        config = dict(self.config, placements={'example': [{'asin': 'B012345678', 'title': '<Test SSD>', 'reason': 'Check capacity & compatibility.'}]})
        source = '<header class="reading-header"></header><section class="source-box"></section>'
        output = apply_affiliates(source, 'example', config)
        self.assertIn('&lt;Test SSD&gt;', output)
        self.assertIn('tag=example-20', output)
        self.assertLess(output.index('Affiliate disclosure'), output.index('Products mentioned'))
        with self.assertRaises(ValueError):
            apply_affiliates('<header class="reading-header"></header>', 'example', config)

    def test_invalid_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'affiliate.json'
            path.write_text(json.dumps({'marketplace': None, 'tracking_id': None, 'placements': {}}))
            self.assertIsNone(load_affiliates(path, {'example'}))
            for config in [dict(self.config, marketplace='amazon.com.evil.test'), dict(self.config, tracking_id='bad?tag=x'), dict(self.config, placements={'missing': []})]:
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    load_affiliates(path, {'example'})


if __name__ == '__main__':
    unittest.main()
