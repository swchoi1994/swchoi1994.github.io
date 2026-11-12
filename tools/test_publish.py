"""Publication acceptance checks: discoverability, preserved content and affiliate boundaries."""
import html
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
        featured = home[home.index('id="featured-title"'):home.index('id="latest-title"')]
        self.assertEqual(re.findall(r'<span class="post-label">(.*?)</span>', featured), [name for name, ids in publish.AI_PICKS for _ in ids])
        for wanted in ('data-view-set="cards"', 'data-view-set="list"', 'id="videos-title"', 'i.ytimg.com/vi/', 'role="search"'):
            self.assertIn(wanted, home)

    def test_articles_keep_sources_dates_and_have_relevant_navigation(self):
        for post in self.posts:
            source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
            schemas = [json.loads(m[1]) for m in publish.LD.finditer(source)]
            data = next(s for s in schemas if s.get('@type') == 'BlogPosting')
            original = f'https://blog.naver.com/swchoi1994/{post["slug"].split("-")[1]}'
            self.assertEqual(data['datePublished'], post['schema']['datePublished'])
            self.assertGreaterEqual(data['dateModified'], data['datePublished'])
            self.assertEqual(data.get('citation'), post['schema'].get('citation'))
            self.assertEqual(data['headline'], post['title'])
            self.assertEqual(data['isBasedOn']['url'], original)
            self.assertEqual(data['isPartOf']['name'], publish.BRAND)
            self.assertIn(f'/topics/{post["topic"]}/', source)
            self.assertIn('At a glance', source)
            self.assertIn('Keep reading', source)
            self.assertIn(original, source)
            self.assertIn('Editorial policy', source)
            self.assertIn(f'<meta property="og:site_name" content="{publish.BRAND}">', source)
            self.assertNotIn('IT Blog', source)

    def test_all_articles_are_in_search_archive_and_sitemap(self):
        index = json.loads((publish.OUT / 'blog/search-index.json').read_text())
        self.assertEqual({p['url'] for p in index}, {p['url'] for p in self.posts})
        self.assertTrue(all(p['topic'] and p['topic_url'] and 'image' not in p for p in index))
        archive = (publish.OUT / 'blog/index.html').read_text()
        archive += ''.join(p.read_text() for p in (publish.OUT / 'blog/page').glob('*/index.html'))
        for post in self.posts:
            self.assertIn(post['url'], archive)
        sitemap = ET.parse(publish.OUT / 'sitemap.xml')
        entries = {node.findtext('{*}loc'): node.findtext('{*}lastmod') for node in sitemap.findall('.//{*}url')}
        self.assertEqual(len(entries), len(list(publish.OUT.rglob('index.html'))))
        for post in self.posts:
            self.assertEqual(entries[publish.SITE + post['url']], post['date'][:10])
        self.assertEqual(entries[publish.SITE + '/'], self.posts[0]['date'][:10])
        feed = ET.parse(publish.OUT / 'blog/feed.xml')
        self.assertEqual(feed.findtext('./channel/title'), publish.BRAND)
        self.assertIn('pub-5340843733211852', (publish.OUT / 'ads.txt').read_text())
        guide = (publish.OUT / 'llms.txt').read_text()
        for slug in (slug for _, ids in publish.AI_PICKS for slug in ids):
            self.assertIn(f'{publish.SITE}/blog/posts/{slug}/', guide, slug)
        for slug in publish.TOPICS:
            self.assertIn(f'{publish.SITE}/topics/{slug}/', guide, slug)

    def test_naver_only_articles_stay_off_the_english_site(self):
        skipped = [slug for slug, _ in publish.SKIPPED]
        self.assertTrue(skipped, 'expected the Korean tax and welfare posts to be recognised')
        self.assertFalse(set(skipped) & {p['slug'] for p in self.posts})
        everything = ''.join((publish.OUT / name).read_text() for name in ('sitemap.xml', 'blog/feed.xml', 'blog/search-index.json', 'index.html', 'blog/index.html'))
        for slug in skipped:
            self.assertFalse((publish.OUT / 'blog/posts' / slug).exists(), slug)
            self.assertNotIn(slug, everything)
        korean = {'citation': ['https://www.nts.go.kr/a', 'https://example.com/b']}
        news = {'citation': ['https://www.hani.co.kr/a', 'https://www.anthropic.com/b']}
        self.assertTrue(publish.naver_only('naver-1', korean, ''))
        self.assertTrue(publish.naver_only('naver-1', {}, '<section class="source-box"><a href="https://cyber.kepco.co.kr/x">x</a></section>'))
        self.assertFalse(publish.naver_only('naver-1', news, ''))
        self.assertFalse(publish.naver_only('naver-1', {'citation': ['https://fakego.kr/a']}, ''))

    def test_titles_and_descriptions_fit_search_results(self):
        self.assertEqual(publish.short_title('Claude Sonnet 4.5 retires on November 30: Check the model IDs in use first'), 'Claude Sonnet 4.5 retires on November 30')
        self.assertEqual(publish.short_title('Wi-Fi connected but no internet? Check these three places and then restart everything'), 'Wi-Fi connected but no internet?')
        self.assertEqual(publish.short_title('Short title'), 'Short title')
        self.assertEqual(publish.document_title('Gmail filters'), 'Gmail filters | Seongwoo Choi Journal')
        long = 'First sentence is here. ' + 'word ' * 60
        self.assertLessEqual(len(publish.clip(long)), 160)
        self.assertEqual(publish.clip('Already short.'), 'Already short.')
        fitting = 0
        for post in self.posts:
            source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
            title = re.search(r'<title>(.*?)</title>', source, re.S)[1]
            description = re.search(r'<meta name="description" content="([^"]*)"', source)[1]
            self.assertLessEqual(len(html.unescape(description)), 160, post['slug'])
            fitting += len(title) <= 60
        self.assertGreater(fitting, len(self.posts) // 2)

    def test_body_transforms_keep_text_and_add_structure(self):
        steps = '<p>Intro</p><p>① First</p>\n<p>② Second <a href="/x">link</a></p><p>③ Third</p><p>After</p>'
        self.assertEqual(publish.numbered_steps(steps), '<p>Intro</p><ol><li>First</li><li>Second <a href="/x">link</a></li><li>Third</li></ol><p>After</p>')
        self.assertEqual(publish.numbered_steps('<p>② Starts late</p><p>③ Next</p>'), '<p>② Starts late</p><p>③ Next</p>')
        body = '<p>See <a href="https://a.test/doc" rel="x">The official guide <span aria-hidden="true">↗</span></a>.</p><section class="source-box"><ul><li><a href="https://a.test/doc" rel="x">a.test/doc <span aria-hidden="true">↗</span></a></li><li><a href="https://b.test/">b.test <span aria-hidden="true">↗</span></a></li></ul></section>'
        named = publish.named_sources(body)
        self.assertIn('<li><a href="https://a.test/doc" rel="x">The official guide ', named)
        self.assertIn('>b.test ', named)

    def test_optional_features_stay_off_until_configured(self):
        article = (publish.OUT / self.posts[0]['url'].lstrip('/') / 'index.html').read_text()
        self.assertNotIn('<ins class="adsbygoogle"', article)
        self.assertNotIn('data-comments', article)
        self.assertIn('id="ad-note"', article)
        self.assertIn('data-theme-toggle', article)
        saved = dict(publish.CONFIG)
        try:
            publish.CONFIG.update(ads={'rail': '1234567890'}, comments={'repo': 'o/r', 'repo_id': 'R_1', 'category': 'General', 'category_id': 'C_1'})
            self.assertIn('data-ad-slot="1234567890"', publish.ad('rail'))
            self.assertEqual(publish.ad('footer'), '')
            self.assertIn('data-repo-id="R_1"', publish.comments())
        finally:
            publish.CONFIG.clear()
            publish.CONFIG.update(saved)

    def test_information_pages_keep_the_ad_free_boundary(self):
        for name in ('about', 'contact', 'editorial', 'privacy'):
            with self.subTest(page=name):
                source = (publish.OUT / 'blog' / name / 'index.html').read_text()
                self.assertNotIn('adsbygoogle', source)
                self.assertNotIn('id="ad-note"', source)
                self.assertIn('G-BLKN59SYTQ', source)

    def test_configured_ad_slots_do_not_enable_information_page_ads(self):
        saved_config, saved_out = dict(publish.CONFIG), publish.OUT
        try:
            publish.CONFIG['ads'] = {'rail': '1234567890', 'footer': '0987654321'}
            with tempfile.TemporaryDirectory() as directory:
                publish.OUT = Path(directory)
                for name in ('about', 'contact', 'editorial', 'privacy'):
                    publish.info_page(publish.ROOT / 'blog' / name / 'index.html', self.posts)
                    source = (publish.OUT / 'blog' / name / 'index.html').read_text()
                    with self.subTest(page=name):
                        self.assertNotIn('adsbygoogle', source)
                        self.assertNotIn('id="ad-note"', source)
                        self.assertNotIn('data-ad-slot=', source)
                editorial = publish.page('Journal', 'Articles', '/blog/', '<h1>Journal</h1>')
                self.assertEqual(editorial.count('pagead/js/adsbygoogle.js'), 1)
                self.assertIn('data-ad-slot="1234567890"', editorial)
                self.assertIn('data-ad-slot="0987654321"', editorial)
                self.assertIn('id="ad-note"', editorial)
        finally:
            publish.CONFIG.clear()
            publish.CONFIG.update(saved_config)
            publish.OUT = saved_out

    def test_localization_preserves_original_and_unknown_destinations(self):
        source = '<a href="https://blog.naver.com/swchoi1994/111">current</a><a href="https://blog.naver.com/swchoi1994/222">next</a><a href="https://blog.naver.com/swchoi1994/333">missing</a>'
        output = publish.localize_links(source, 'naver-111', {'naver-111', 'naver-222'})
        self.assertIn('href="/blog/posts/naver-222/"', output)
        self.assertIn('https://blog.naver.com/swchoi1994/111', output)
        self.assertIn('https://blog.naver.com/swchoi1994/333', output)

    def test_classifier_keeps_reader_intent(self):
        for title, topic in [('Windows Update fails', 'windows'), ('Gmail filters', 'google-tools'), ('Excel SUMIFS #VALUE! error', 'office-documents'), ('Cloud sync and backup', 'privacy-backup'), ('Claude Skills', 'ai-automation'),
                             ('How to check a Windows Wi-Fi password: Select Show', 'windows'), ('Create a Table of Contents in Word: Heading Styles', 'office-documents'),
                             ('How to check and organize devices signed in to your Google account', 'privacy-backup'), ('Apple revises App Review Guidelines', 'ai-automation'),
                             ('How to check the meaning of OneDrive icons: Read sync status', 'privacy-backup'), ('What to check when a PDF will not upload to Gemini Notebook', 'ai-automation'),
                             ('How to restore the default PDF app', 'office-documents')]:
            self.assertEqual(publish.topic_for(title), topic)

    def test_article_images_reach_search_and_social_previews(self):
        for post in self.posts:
            image = post['image']
            social = publish.social_image(post)
            source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
            self.assertNotIn('<details class="article-illustration">', source)
            self.assertTrue((publish.OUT / image['src'].lstrip('/')).is_file())
            self.assertTrue((publish.OUT / social['src'].lstrip('/')).is_file())
            self.assertFalse(social['src'].endswith('.svg'), post['slug'])
            schemas = [json.loads(m[1]) for m in publish.LD.finditer(source)]
            article = next(s for s in schemas if s.get('@type') == 'BlogPosting')
            self.assertEqual(article['image'], publish.SITE + social['src'])
            self.assertIn(f'<meta property="og:image" content="{publish.SITE}{social["src"]}">', source)
            self.assertIn(f'<meta property="og:image:width" content="{social["width"]}">', source)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', source)
            # The cover is a social preview by default; content/site.json can show it in the article.
            self.assertEqual('class="article-cover"' in source, bool(publish.CONFIG.get('article_cover')))
            if image.get('small'):
                self.assertTrue((publish.OUT / image['small'].lstrip('/')).is_file())
                self.assertLess((publish.OUT / image['src'].lstrip('/')).stat().st_size, 300_000)

    def test_reference_screenshots_keep_attribution_and_original_files(self):
        references = [p for p in self.posts if p['image'].get('reference')]
        self.assertTrue(references)
        for post in references:
            image = post['image']['reference']
            source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
            self.assertEqual(source.count('class="article-reference"'), 1)
            self.assertIn(image['src'], source)
            self.assertIn(image['source_url'], source)
            self.assertIn(image['permission_url'], source)
            self.assertIn('Used with permission from Microsoft.', source)
            self.assertLess(source.index('class="article-reference"'), source.index('class="source-box"'))
            path = image['src'].lstrip('/')
            self.assertEqual((publish.OUT / path).read_bytes(), (publish.ROOT / path).read_bytes())


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
