"""Publication acceptance checks: discoverability, preserved content and affiliate boundaries."""
import datetime
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import urljoin, urlsplit, unquote, parse_qs
import xml.etree.ElementTree as ET

import indexnow
import publish
import trends
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
            self.assertEqual(data['datePublished'], post['schema']['datePublished'])
            self.assertGreaterEqual(data['dateModified'], data['datePublished'])
            self.assertEqual(data.get('citation'), post['schema'].get('citation'))
            self.assertEqual(data['headline'], post['title'])
            if post.get('native'):
                # Written here: no Korean original, so nothing may claim one.
                self.assertNotIn('isBasedOn', data)
                self.assertNotIn('blog.naver.com/swchoi1994/', source[source.index('<main'):source.index('</main>')])
                self.assertIn('Written for this site with AI assistance', source)
            else:
                original = f'https://blog.naver.com/swchoi1994/{post["slug"].split("-")[1]}'
                self.assertEqual(data['isBasedOn']['url'], original)
                self.assertIn(original, source)
            # A series article belongs to the journal and to its series; every other article to the journal alone.
            parents = data['isPartOf'] if isinstance(data['isPartOf'], list) else [data['isPartOf']]
            self.assertEqual(parents[0]['name'], publish.BRAND)
            self.assertEqual(len(parents), 2 if post.get('series') else 1)
            self.assertIn(f'/topics/{post["topic"]}/', source)
            self.assertIn('At a glance', source)
            self.assertIn('Keep reading', source)
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

    def test_articles_written_here_meet_the_publishing_bar(self):
        written = [p for p in self.posts if p.get('native')]
        self.assertTrue(written, 'expected at least one article under content/posts/')
        feed = (publish.OUT / 'blog/feed.xml').read_text()
        home = (publish.OUT / 'index.html').read_text()
        for post in written:
            with self.subTest(article=post['slug']):
                source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
                # These are ours to get right: titles and descriptions must fit a search result as written.
                self.assertLessEqual(len(post['title']), 60)
                self.assertLessEqual(len(post['description']), 160)
                self.assertGreaterEqual(len(post['native']['sources']), 2)
                for cited in post['native']['sources']:
                    self.assertTrue(cited['url'].startswith('https://'))
                    self.assertIn(html.escape(cited['url']), source)
                self.assertTrue(post['native']['note'], 'say how the article was checked')
                self.assertGreaterEqual(len(re.findall(r'<h2 id="', post['native']['body'])), 3)
                self.assertIn(publish.SITE + post['url'], feed)
        self.assertIn(written[0]['url'], home)

    def test_series_are_read_in_order_and_link_their_parts(self):
        groups = publish.series_parts(self.posts)
        self.assertTrue(groups, 'expected at least one series in content/series.json with articles')
        index = (publish.OUT / 'series/index.html').read_text()
        guide = (publish.OUT / 'llms.txt').read_text()
        for slug, members in groups.items():
            self.assertEqual([p['part'] for p in members], list(range(1, len(members) + 1)))
            hub = (publish.OUT / 'series' / slug / 'index.html').read_text()
            self.assertIn(f'/series/{slug}/', index)
            self.assertIn(html.escape(publish.SERIES[slug]['title']), hub)
            # The hub lists the parts in reading order, not by date.
            self.assertEqual(re.findall(r'<span class="post-label">Part (\d+)</span>', hub), [str(p['part']) for p in members])
            for number, post in enumerate(members):
                with self.subTest(series=slug, part=post['part']):
                    self.assertIn(post['url'], hub)
                    self.assertIn(publish.SITE + post['url'], guide)
                    source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
                    self.assertIn(f'Series · part {post["part"]} of {len(members)}', source)
                    self.assertEqual(source.count('aria-current="step"'), 1)
                    navigation = re.search(r'<nav class="series-nav".*?</nav>', source, re.S)[0]
                    self.assertEqual('rel="prev"' in navigation, number > 0)
                    self.assertEqual('rel="next"' in navigation, number + 1 < len(members))
                    if number:
                        self.assertIn(f'rel="prev" href="{members[number - 1]["url"]}"', navigation)
                    if number + 1 < len(members):
                        self.assertIn(f'rel="next" href="{members[number + 1]["url"]}"', navigation)
                    data = next(json.loads(m[1]) for m in publish.LD.finditer(source) if '"BlogPosting"' in m[1])
                    self.assertEqual(data['position'], post['part'])
                    self.assertEqual(data['isPartOf'][1]['url'], f'{publish.SITE}/series/{slug}/')
        # An article outside any series shows no series furniture.
        plain = next(p for p in self.posts if not p.get('series'))
        source = (publish.OUT / plain['url'].lstrip('/') / 'index.html').read_text()
        self.assertNotIn('series-box', source)
        self.assertNotIn('series-nav', source)

    def test_a_series_with_a_gap_or_a_repeat_stops_the_build(self):
        parts = [dict(series='s', part=1, slug='a'), dict(series='s', part=3, slug='b')]
        with self.assertRaises(ValueError):
            publish.series_parts(parts)
        with self.assertRaises(ValueError):
            publish.series_parts([dict(series='s', part=1, slug='a'), dict(series='s', part=1, slug='b')])

    def test_projects_say_what_is_needed_and_what_results(self):
        projects = [p for p in self.posts if p.get('project')]
        self.assertTrue(projects)
        listing = (publish.OUT / 'projects/index.html').read_text()
        for post in projects:
            with self.subTest(project=post['slug']):
                source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
                for page in (listing, source):
                    self.assertIn(html.escape(post['project']['needs']), page)
                    self.assertIn(html.escape(post['project']['result']), page)
                self.assertIn(post['url'], listing)
        home = (publish.OUT / 'index.html').read_text()
        for href in ('/series/', '/projects/'):
            self.assertIn(f'<a href="{href}"><span>', home, 'the sidebar links to series and projects')
        self.assertIn('id="series-title"', home)

    def test_search_engine_verification_is_home_only_and_off_until_set(self):
        self.assertNotIn('google-site-verification', (publish.OUT / 'index.html').read_text())
        saved = dict(publish.CONFIG)
        try:
            publish.CONFIG['verification'] = {'google': 'abc"123', 'bing': '', 'other': 'x'}
            home = publish.page('Home', 'Description', '/', '<h1>Home</h1>')
            self.assertIn('<meta name="google-site-verification" content="abc&quot;123">', home)
            self.assertNotIn('msvalidate.01', home)
            self.assertNotIn('google-site-verification', publish.page('Other', 'Description', '/blog/', '<h1>Other</h1>'))
        finally:
            publish.CONFIG.clear()
            publish.CONFIG.update(saved)

    def test_cards_carry_a_picture_and_articles_can_embed_figures(self):
        self.assertTrue(publish.CONFIG.get('card_covers'), 'content/site.json turns card pictures on')
        archive = (publish.OUT / 'blog/index.html').read_text()
        cards = re.findall(r'<article class="post">.*?</article>', archive, re.S)
        self.assertEqual(len(cards), publish.PAGE_SIZE)
        for card in cards:
            self.assertEqual(card.count('class="post-cover'), 1)
            # Decorative: the title is right below, so the picture carries no alt text of its own.
            self.assertTrue('alt=""' in card or 'aria-hidden="true"' in card)
        for post in self.posts:
            cover = publish.card_cover(post)
            if post['image'].get('small') and not post['image']['src'].endswith('.svg'):
                self.assertIn(post['image']['small'], cover)
                self.assertIn('loading="lazy"', cover)
            else:
                self.assertIn('<svg viewBox="0 0 320 180"', cover, post['slug'])
        # Each article written here picks its own motif, so a page of them is not one picture repeated.
        written = [p for p in self.posts if p.get('native')]
        self.assertTrue(all(p.get('cover') in publish.MOTIFS for p in written), [p['slug'] for p in written if not p.get('cover')])
        self.assertGreaterEqual(len({p['cover'] for p in written}), 8)
        saved = dict(publish.CONFIG)
        try:
            publish.CONFIG['card_covers'] = False
            self.assertEqual(publish.card_cover(self.posts[0]), '')
        finally:
            publish.CONFIG.clear()
            publish.CONFIG.update(saved)
        # A video placeholder becomes a still image and a button; no player loads until the reader asks.
        body = publish.native_body(dict(body='<p>Intro</p>{{video:vLP_8hLBs-U|A "quoted" title}}', sources=[], note=''))
        self.assertIn('data-video="vLP_8hLBs-U"', body)
        self.assertIn('A &quot;quoted&quot; title', body)
        self.assertNotIn('<iframe', body)
        self.assertNotIn('{{video', body)

    def test_trend_ranking_counts_each_story_for_the_most_specific_name(self):
        terms = [{'term': 'Claude Code'}, {'term': 'Claude'}, {'term': 'MCP', 'match': '(?-i:MCP)|model context protocol'},
                 {'term': 'vLLM'}, {'term': 'LLMs', 'match': 'llms?'}, {'term': 'Qwen'}]
        stories = [{'title': 'Claude Code ships a new hook', 'points': 300},      # Claude Code, not also Claude
                   {'title': 'Why I left Claude', 'points': 120},
                   {'title': 'MCP Explained', 'points': 90},
                   {'title': 'The mcp command on Plan 9', 'points': 500},        # lower case: not the protocol
                   {'title': 'Serving LLMs with vLLM', 'points': 40}]            # two names; "vLLM" is not "LLM"
        discussed = trends.rank(stories, terms, {'Google': {'claude', 'mcp', 'weather'}, 'Grokipedia': {'Claude', 'MCP', 'Claude Code review'}})
        self.assertEqual([(row['term'], row['points'], row['stories']) for row in discussed],
                         [('Claude Code', 300, 1), ('Claude', 120, 1), ('MCP', 90, 1), ('LLMs', 40, 1), ('vLLM', 40, 1)])
        self.assertEqual({row['term']: row['also'] for row in discussed if row['also']}, {'Claude': ['Google', 'Grokipedia'], 'MCP': ['Grokipedia']})
        # A name that begins longer names leaves them out of its news search.
        self.assertEqual(trends.news_query({'term': 'Claude', 'news': '"Claude" Anthropic'}, terms), '"Claude" Anthropic -"Claude Code"')
        self.assertEqual(trends.news_query({'term': 'vLLM'}, terms), '"vLLM"')
        # A busy name fills the 100-article feed, so it is counted over a shorter window and scaled to a day.
        feeds = iter(['<item>' * 100, '<item>' * 100, '<item>' * 7])
        self.assertEqual(trends.news_rate('"Busy"', fetch=lambda url: next(feeds)), 7 * 24)
        self.assertEqual(trends.news_rate('"Quiet"', fetch=lambda url: '<item>' * 12), 12)

    def test_trend_score_averages_each_source_and_survives_a_missing_one(self):
        discussed = [{'term': 'A', 'points': 300, 'stories': 3, 'also': []}, {'term': 'B', 'points': 100, 'stories': 1, 'also': []}]
        both = trends.blend(discussed, {'A': 10, 'B': 10, 'C': 80})
        # A: 75% of points, 10% of news. B: 25%, 10%. C: none, 80%.
        self.assertEqual([(row['term'], row['score']) for row in both], [('A', 42.5), ('C', 40.0), ('B', 17.5)])
        self.assertEqual(both[1]['points'], 0)
        alone = trends.blend(discussed, {})
        self.assertEqual([(row['term'], row['score'], row['news']) for row in alone], [('A', 75.0, None), ('B', 25.0, None)])

    def test_trending_box_needs_a_fresh_ranking_and_links_names_to_our_pages(self):
        now = datetime.datetime(2026, 11, 12, 12, tzinfo=datetime.timezone.utc)
        names = ['Claude Code', 'vLLM', 'Not written yet', 'MCP', 'Gemini', 'NVIDIA']
        saved = {'updated': '2026-11-12T06:00:00+00:00', 'days': 7, 'sources': ['Hacker News', 'Google News'],
                 'items': [{'term': name, 'score': 40 - 5 * n, 'points': 100, 'stories': 2, 'news': 10, 'also': ['Google', 'Grokipedia'] if n == 0 else []} for n, name in enumerate(names)]}
        trend = publish.trend_ranking(saved, now)
        box = publish.trending_box(trend, {'Claude Code': {'url': '/trending/claude-code/'}, 'vLLM': {'url': '/trending/vllm/'}})
        self.assertEqual(re.findall(r'<li><(?:a href="[^"]*"|span)>([^<]+)<', box), names)
        self.assertIn('<a href="/trending/claude-code/">Claude Code</a>', box)
        self.assertIn('<span>Not written yet</span>', box)
        self.assertEqual(re.findall(r'class="trend-tag"[^>]*>([^<]+)<', box), ['Google', 'Grokipedia'])
        self.assertIn('Hacker News and Google News', box)
        self.assertIn('<time datetime="2026-11-12T06:00:00+00:00">12 Nov 2026, 06:00 UTC</time>', box)
        # Too old, missing or too short: no box, so the home page never shows a stale "trend".
        self.assertEqual(publish.trend_ranking(saved, now + datetime.timedelta(days=5))['rows'], [])
        self.assertEqual(publish.trend_ranking({}, now)['rows'], [])
        self.assertEqual(publish.trending_box(dict(trend, rows=trend['rows'][:4]), {}), '')

    def test_each_watchlist_name_we_cover_has_a_page_with_articles_and_channel_videos(self):
        terms = json.loads((publish.ROOT / 'content/trend-terms.json').read_text())
        names = [entry['term'] for entry in terms]
        self.assertEqual(len(names), len(set(names)), 'a name appears twice on the watchlist')
        video = ('<article class="media-item"><div><p class="post-meta">AI2Now · 2026.11.10</p><h3>Nvidia Blackwell: the chip on stage</h3><p>A short documentary.</p>'
                 '<div class="video-space"><button type="button" class="video-load" data-video="vLP_8hLBs-U">▶ Watch on YouTube</button></div></div></article>')
        other = '<article class="media-item"><img class="" src="/x.jpg" alt=""><div><h3>IKEA began as pens</h3><p>History.</p></div></article>'
        hubs = publish.trend_hubs(self.posts, [other, video])
        self.assertEqual(hubs['NVIDIA']['clips'], [video])
        self.assertEqual(hubs['NVIDIA']['articles'][0]['slug'], 'a100-l40s-h100-inference')   # pinned articles lead
        pinned = next(entry for entry in terms if entry['term'] == 'vLLM')['pin']
        self.assertEqual([p['slug'] for p in hubs['vLLM']['articles'][:len(pinned)]], pinned)
        poster = publish.clip_with_poster(video)
        self.assertIn('<article class="media-item"><div class="video-space"><button type="button" class="video-load video-poster" data-video="vLP_8hLBs-U"', poster)
        self.assertNotIn('<iframe', poster)       # the player still loads only on click
        self.assertEqual(publish.clip_with_poster(other), other)
        index = (publish.OUT / 'trending/index.html').read_text()
        self.assertIn('How the ranking works', index)
        linked = set(re.findall(r'href="(/trending/[a-z0-9-]+/)"', index))
        self.assertTrue(linked)
        for href in linked:
            self.assertTrue((publish.OUT / href.strip('/') / 'index.html').is_file(), href)
        page = (publish.OUT / 'trending/claude-code/index.html').read_text()
        self.assertIn('/blog/posts/claude-code-plugins-mcp-terminal/', page)
        self.assertIn('<a href="/trending/"><span>', (publish.OUT / 'index.html').read_text())

    def test_articles_written_here_say_up_front_what_was_tested(self):
        native = [p for p in self.posts if p.get('native')]
        self.assertTrue(native)
        home = (publish.OUT / 'blog/index.html').read_text()
        for post in native:
            level, line = post['checked']['level'], post['checked']['line']
            self.assertIn(level, publish.CHECK_LABELS, post['slug'])
            page = (publish.OUT / post['url'].strip('/') / 'index.html').read_text()
            # The statement sits in the header, before the body, with its label.
            header = page[page.index('<header class="reading-header">'):page.index('<div class="reading-body">')]
            self.assertIn(f'<p class="checked checked-{level}"><strong>{publish.CHECK_LABELS[level]}</strong><span>{html.escape(line)}</span></p>', header, post['slug'])
            # "Not tested" must never be dressed up: an article that ran nothing admits it in the same line.
            if level == 'read':
                self.assertRegex(line, r'(?i)\bnot?\b|\bnothing\b|\bnone\b|summary|overview|explanation', post['slug'])
        tested = next(p for p in native if p['checked']['level'] == 'tested')
        unread = next(p for p in native if p['checked']['level'] == 'read')
        self.assertIn('<span class="post-check"> · <b>Tested</b></span>', publish.card(tested))
        self.assertNotIn('post-check', publish.card(unread))
        synced = next(p for p in self.posts if not p.get('native'))
        self.assertNotIn('post-check', publish.card(synced))
        self.assertNotIn('class="checked', (publish.OUT / synced['url'].strip('/') / 'index.html').read_text())

    def test_release_explainers_are_listed_newest_announcement_first(self):
        covered = [p for p in self.posts if p.get('release')]
        self.assertTrue(covered, 'expected at least one article with release metadata')
        listing = (publish.OUT / 'releases/index.html').read_text()
        rows = re.findall(r'<tr><td><time datetime="([^"]+)">', listing)
        self.assertEqual(rows, sorted((p['release']['announced'] for p in covered), reverse=True))
        for post in covered:
            self.assertIn(post['url'], listing)
            self.assertIn(html.escape(post['release']['name']), listing)
            # Facts about a release come from the company itself: at least one source on its own domain.
            domains = publish.COMPANY_DOMAINS.get(post['release']['company'])
            self.assertTrue(domains, f'add {post["release"]["company"]} to COMPANY_DOMAINS so its sources are checked')
            if domains:
                self.assertTrue(any(urlsplit(src['url']).netloc.endswith(domains) for src in post['native']['sources']), post['slug'])
        self.assertIn('<a href="/releases/"><span>', (publish.OUT / 'index.html').read_text())

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
        self.assertEqual(publish.scrollable_tables('<p>a</p><table><tr><td>1</td></tr></table>'),
                         '<p>a</p><div class="table-scroll" tabindex="0" role="region" aria-label="Table"><table><tr><td>1</td></tr></table></div>')

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

    def test_ad_blocker_wall_follows_the_owner_setting(self):
        saved = dict(publish.CONFIG)
        try:
            publish.CONFIG['adblock_wall'] = True
            walled = publish.page('Journal', 'Articles', '/blog/', '<h1>Journal</h1>')
            self.assertEqual(walled.count('id="ad-wall"'), 1)
            self.assertIn('data-ad-wall-reload', walled)
            # The wall sits outside the page shell it pauses, and offers a way to report a false alarm.
            self.assertGreater(walled.index('id="ad-wall"'), walled.index('class="site-footer"'))
            self.assertIn('href="/blog/contact/"', walled[walled.index('id="ad-wall"'):])
            self.assertNotIn('id="ad-wall"', publish.page('About', 'About', '/blog/about/', '<h1>About</h1>', ads=False))
            publish.CONFIG['adblock_wall'] = False
            polite = publish.page('Journal', 'Articles', '/blog/', '<h1>Journal</h1>')
            self.assertNotIn('id="ad-wall"', polite)
            self.assertIn('id="ad-note"', polite)
        finally:
            publish.CONFIG.clear()
            publish.CONFIG.update(saved)
        for name in ('about', 'contact', 'editorial', 'privacy'):
            self.assertNotIn('ad-wall', (publish.OUT / 'blog' / name / 'index.html').read_text(), name)

    def test_articles_offer_sharing_and_following(self):
        post = self.posts[0]
        source = (publish.OUT / post['url'].lstrip('/') / 'index.html').read_text()
        self.assertIn('https://x.com/intent/post?url=https%3A%2F%2Fswchoi1994.github.io%2Fblog%2Fposts%2F', source)
        self.assertIn('https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2F', source)
        self.assertIn(f'href="{publish.X_PROFILE}"', source)

    def test_indexnow_submits_only_recently_changed_pages(self):
        sitemap = (publish.OUT / 'sitemap.xml').read_bytes()
        newest = datetime.date.fromisoformat(self.posts[0]['date'][:10])
        urls = indexnow.recent(sitemap, newest)
        self.assertIn(publish.SITE + self.posts[0]['url'], urls)
        self.assertIn(publish.SITE + '/', urls)
        self.assertNotIn(publish.SITE + '/blog/about/', urls)
        self.assertEqual(indexnow.recent(sitemap, newest + datetime.timedelta(days=30)), [])
        self.assertEqual((publish.ROOT / f'{indexnow.KEY}.txt').read_text().strip(), indexnow.KEY)

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
            # content/site.json decides whether a cover opens the article, and only a real illustration qualifies:
            # never the site's own card (articles written here) or an upstream text graphic.
            illustrated = not post.get('native') and not image['src'].endswith('.svg')
            self.assertEqual('class="article-cover"' in source, bool(publish.CONFIG.get('article_cover')) and illustrated, post['slug'])
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
