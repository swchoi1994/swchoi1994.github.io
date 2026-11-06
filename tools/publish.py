#!/usr/bin/env python3
"""Render the publication around upstream-synced HTML; never modify sync inputs."""
import html
import json
import math
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from affiliates import apply_affiliates, load_affiliates

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '_site'
SITE = 'https://swchoi1994.github.io'
NAME = 'Seongwoo Choi'
BRAND = 'Seongwoo Choi / Journal'
PAGE_SIZE = 12
TOPICS = {
    'ai-automation': ('AI & technology', 'Understand AI tools, build useful workflows, and check what a new release actually changes.'),
    'windows': ('Windows', 'Find the cause before changing settings. Practical help with devices, updates, performance, and recovery.'),
    'google-tools': ('Google tools', 'Get more out of Gmail, Drive, Calendar, and Docs, with clear steps and links to the official sources.'),
    'office-documents': ('Office & documents', 'Fix spreadsheet errors, work with PDFs, and keep your documents accurate.'),
    'privacy-backup': ('Privacy & backup', 'Protect your accounts and files. Understand permissions, recovery options, and the limits of cloud sync.'),
}
# Editorial selections, not traffic rankings. IDs remain the upstream article IDs.
PICKS = ['naver-224450802208', 'naver-224449506180', 'naver-224448398835']
STARTERS = ['naver-224459505819', 'naver-224448740524', 'naver-224453047781']
# Owner-chosen AI reading list for the home page: (group heading, upstream article IDs).
AI_PICKS = [
    ('Coding agents', ['naver-224459894229', 'naver-224450802208', 'naver-224460089258']),
    ('AI agent security', ['naver-224443237114', 'naver-224444722682', 'naver-224445242655']),
    ('Model costs and APIs', ['naver-224458624841', 'naver-224447760925', 'naver-224447373831']),
    ('Local AI and hardware', ['naver-224443239521', 'naver-224444693710', 'naver-224459303987']),
    ('Using AI safely at work', ['naver-224448867391', 'naver-224449083135', 'naver-224449619760']),
]
TITLES = {
    'naver-224450802208': 'Claude Skills explained: official and community resources',
    'naver-224449506180': 'Cloud sync vs. backup: protect your files with the 3-2-1 rule',
    'naver-224448398835': 'Blog automation: three errors I hit and how I fixed them',
    'naver-224459505819': 'Claude Code: installation and first login',
    'naver-224448740524': 'Passkeys, passwords, and 2-step verification explained',
    'naver-224453047781': 'Organize receipt emails with Gmail filters',
    'naver-224467696426': 'CHKDSK explained: when to use /f, /r, or /scan',
    'naver-224467908517': 'Check laptop battery health with a Windows battery report',
    'naver-224467587320': 'Stop Windows Update restarting during your active hours',
    'naver-224467474821': 'Gmail: blocking a sender vs. reporting spam',
    'naver-224467329568': 'Gmail Undo Send: set your cancellation window',
    'naver-224467167551': 'How to find your BitLocker recovery key',
    'naver-224467023835': 'Wi-Fi connected but no internet? Check these three places',
    'naver-224466875643': 'Forgot your Windows PIN? Three reset paths',
}
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
e = html.escape


def structured(value):
    return '<script type="application/ld+json">' + json.dumps(value, ensure_ascii=False).replace('<', '\\u003c') + '</script>'


def topic_for(title):
    text = title.lower()
    if re.search(r'backup|bitlocker|passkey|2-step|personal information|privacy|permissions|quarantin|isolated files|quick assist|firewall|chatgpt memory|delete gemini|delete chatgpt', text):
        return 'privacy-backup'
    if re.search(r'gmail|google (drive|calendar|docs|storage)', text):
        return 'google-tools'
    if re.search(r'excel|word:|powerpoint|pdf|ocr|scanning documents', text) and not re.search(r'\bai\b|chatgpt', text):
        return 'office-documents'
    if re.search(r'windows|laptop|bluetooth|wi-fi|monitor|task manager|battery|volume mixer|microphone|off-screen', text) and not re.search(r'ollama|rtx spark', text):
        return 'windows'
    return 'ai-automation'


def load_articles():
    posts = []
    for path in sorted((ROOT / 'blog/posts').glob('*/index.html')):
        source = path.read_text()
        schemas = [json.loads(m[1]) for m in LD.finditer(source)]
        data = next(d for d in schemas if d.get('@type') == 'BlogPosting')
        slug = path.parent.name
        title = TITLES.get(slug, data['headline'])
        posts.append(dict(slug=slug, title=title, description=data['description'],
                          date=data['datePublished'], url=f'/blog/posts/{slug}/',
                          topic=topic_for(data['headline']),
                          minutes=max(1, math.ceil(data.get('wordCount', 600) / 220)),
                          source=source, schema=data))
    if not posts:
        raise ValueError('No published articles found; refusing to publish an empty site')
    return sorted(posts, key=lambda p: (p['date'], p['slug']), reverse=True)


def navigation():
    return '''<a class="skip-link" href="#main-content">Skip to content</a>
<header class="site-header"><nav class="site-nav" aria-label="Main navigation">
<a class="site-brand" href="/"><span>Seongwoo Choi<span class="brand-edition"> / Journal</span></span></a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav-menu" aria-label="Open navigation"><span></span><span></span><span></span></button>
<div class="nav-menu" id="nav-menu"><a class="nav-link" href="/">Home</a><a class="nav-link" href="/topics/">Topics</a><a class="nav-link" href="/guides/">Guides</a><a class="nav-link" href="/blog/about/">About</a><a class="nav-link nav-search" href="/blog/#search">Search <span aria-hidden="true">↗</span></a></div>
</nav></header>'''


def footer():
    return '''<footer class="journal-footer"><div><strong>Seongwoo Choi / Journal</strong><p>Practical technology. Clear context.</p><a href="/blog/feed.xml">Follow new articles via RSS ↗</a></div>
<nav aria-label="Site information"><a href="/portfolio/">Portfolio &amp; CV</a><a href="/videos/">Videos</a><a href="/blog/contact/">Contact &amp; partnerships</a><a href="/blog/editorial/">Editorial policy</a><a href="/blog/privacy/">Privacy</a><a href="https://blog.naver.com/swchoi1994">한국어 · Naver ↗</a></nav>
<small>© Seongwoo Choi. Advertising helps support this independent publication.</small></footer>
<script src="/assets/js/script.js" defer></script><script src="/blog/blog.js" defer></script><script src="/assets/js/publication.js" defer></script>'''


def breadcrumbs(items):
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i, 'name': name, 'item': SITE + path}
        for i, (name, path) in enumerate(items, 1)]}


def collection(title, url, posts):
    return {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': title, 'url': SITE + url,
            'isPartOf': {'@id': SITE + '/#website'}, 'mainEntity': {
                '@type': 'ItemList', 'itemListElement': [
                    {'@type': 'ListItem', 'position': i, 'name': p['title'], 'url': SITE + p['url']}
                    for i, p in enumerate(posts, 1)]}}


ANALYTICS = '''<script async src="https://www.googletagmanager.com/gtag/js?id=G-BLKN59SYTQ"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-BLKN59SYTQ');</script>'''


def add_analytics():
    """Put the GA4 tag in the <head> of every published page except the OpenClaw setup tool."""
    for path in OUT.rglob('*.html'):
        if path.relative_to(OUT).parts[0] == 'openclaw-setup':
            continue
        source = path.read_text()
        if 'G-BLKN59SYTQ' not in source:
            assert source.count('</head>') == 1, path
            path.write_text(source.replace('</head>', ANALYTICS + '\n</head>'))


def page(title, description, url, body, schemas=()):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} | Seongwoo Choi Journal</title><meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}{url}"><meta name="robots" content="index,follow,max-image-preview:large"><meta name="theme-color" content="#f6f4ef">
<meta property="og:type" content="website"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{SITE}{url}"><meta property="og:site_name" content="{BRAND}">
<meta property="og:image" content="{SITE}/assets/img/swc94.png"><meta name="twitter:card" content="summary"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(description)}">
<link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/assets/css/style.css"><link rel="stylesheet" href="/blog/blog.css"><link rel="stylesheet" href="/assets/css/publication.css">
<link rel="alternate" type="application/rss+xml" title="Seongwoo Choi Journal" href="/blog/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&amp;family=Newsreader:opsz,wght@6..72,500;6..72,600&amp;display=swap" rel="stylesheet">
<meta name="google-adsense-account" content="ca-pub-5340843733211852"><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5340843733211852" crossorigin="anonymous"></script>
{''.join(structured(s) for s in schemas)}</head><body class="journal publication">{navigation()}<main id="main-content" class="journal-main">{body}</main>{footer()}</body></html>'''


def write(url, content):
    path = OUT / url.lstrip('/') / 'index.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def meta(post):
    return f'<p class="post-meta"><time datetime="{e(post["date"])}">{post["date"][:10]}</time><span> · {post["minutes"]} min read</span></p>'


def card(post, lead=False):
    label = TOPICS[post['topic']][0]
    return f'''<article class="story{' story-lead' if lead else ''}"><a class="topic-label" href="/topics/{post['topic']}/">{label}</a>
<h{'2' if lead else '3'}><a href="{post['url']}">{e(post['title'])}</a></h{'2' if lead else '3'}><p class="story-description">{e(post['description'])}</p>{meta(post)}<a class="read-link" href="{post['url']}">Read guide <span aria-hidden="true">↗</span><span class="sr-only">: {e(post['title'])}</span></a></article>'''


def topic_links():
    return '<nav class="topic-strip" aria-label="Browse topics">' + ''.join(
        f'<a href="/topics/{slug}/">{name} <span aria-hidden="true">↗</span></a>' for slug, (name, _) in TOPICS.items()) + '</nav>'


def heading(kicker, title, link='', label='View all articles'):
    return f'<div class="section-heading"><div><p class="kicker">{e(kicker)}</p><h2>{e(title)}</h2></div>' + (f'<a class="section-link" href="{link}">{label} ↗</a>' if link else '') + '</div>'


def essentials(groups):
    """The owner's hand-picked AI reading list, grouped by theme."""
    parts = ['<section class="home-section starter-section" aria-labelledby="essentials-title">',
             heading('A useful place to begin', 'Start with the essentials', '/blog/', 'Explore the archive').replace('<h2>', '<h2 id="essentials-title">')]
    for name, members in groups:
        parts.append(f'<h3 class="pick-heading">{e(name)}</h3><div class="story-grid">' + ''.join(card(p) for p in members) + '</div>')
    parts.append('</section>')
    return ''.join(parts)


def home(posts, media):
    by_id = {p['slug']: p for p in posts}
    groups = [(name, [by_id[s] for s in ids]) for name, ids in AI_PICKS]
    chosen = [p for _, members in groups for p in members]
    body = f'''<section class="publication-intro"><p class="kicker">An independent technology journal</p><h1>Make technology<br><em>work for you.</em></h1><div class="intro-bottom"><p>Practical guides to AI, everyday software, and safer digital habits.<br>Clear steps. Original sources. Context that matters.</p><a href="/blog/about/" class="byline">By Seongwoo Choi <span>AI engineer &amp; founder ↗</span></a></div></section>
{topic_links()}{essentials(groups)}
<section class="guide-spotlight"><p class="kicker">For builders</p><h2>Find your next AI coding tool.</h2><p>A guide to agent repositories, skills, and plugins, with dated GitHub star counts and things to check before installing.</p><a class="read-link" href="/guides/ai-coding-agent-repos/">Explore the repository guide ↗</a></section>
<section class="home-section">{heading('Watch & explore', 'From AI2Now', '/videos/', 'All videos & posts')}<div class="media-list">{''.join(media[:2])}</div></section>
<section class="author-strip"><img src="/assets/img/swc94.png" width="96" height="96" loading="lazy" alt="Seongwoo Choi"><div><p class="kicker">Behind the journal</p><h2>Technology, with an engineer’s perspective.</h2><p>I’m Seongwoo Choi, an AI engineer and founder based in Abu Dhabi. This journal brings together practical software guides and technology analysis.</p><a href="/blog/about/">About the author &amp; editorial approach ↗</a></div><a class="rss-link" href="/blog/feed.xml">Keep up with the journal<span>Subscribe via RSS ↗</span></a></section>'''
    person = json.loads(LD.search((ROOT / 'portfolio/index.html').read_text())[1])
    person['url'] = SITE + '/blog/about/'
    schemas = [{'@context': 'https://schema.org', '@type': 'WebSite', '@id': SITE + '/#website', 'url': SITE + '/', 'name': BRAND, 'inLanguage': 'en', 'publisher': {'@id': SITE + '/#person'}}, person,
               {'@context': 'https://schema.org', '@type': 'Blog', '@id': SITE + '/blog/#blog', 'url': SITE + '/', 'name': BRAND, 'author': {'@id': SITE + '/#person'}},
               collection('Start with the essentials: selected AI articles', '/', chosen)]
    write('/', page('Practical AI & technology guides', 'Practical guides to AI, Windows, Google tools, documents, privacy and backup. By AI engineer Seongwoo Choi.', '/', body, schemas))


def archive(posts, base='/blog/', title='All articles', description='Find a useful answer. Browse the latest guides, or search the complete journal.'):
    count = math.ceil(len(posts) / PAGE_SIZE)
    for number in range(1, count + 1):
        url = base if number == 1 else f'{base}page/{number}/'
        batch = posts[(number - 1) * PAGE_SIZE:number * PAGE_SIZE]
        search = '''<form class="archive-search" id="search" role="search"><label for="archive-search">Search the complete journal</label><div><input id="archive-search" type="search" name="q" placeholder="Try Gmail, Claude, backup…" autocomplete="off"><button type="submit">Search</button></div><noscript><p>Search requires JavaScript. All articles are available through the topics and numbered archive pages below.</p></noscript></form><p id="search-status" role="status" aria-live="polite"></p><div id="search-results" class="latest-grid" hidden></div>''' if base == '/blog/' else ''
        pages = ''.join(f'<a href="{base if i == 1 else f"{base}page/{i}/"}"' + (' aria-current="page"' if i == number else '') + f' aria-label="Page {i}">{i}</a>' for i in range(1, count + 1))
        body = f'''<header class="listing-intro"><p class="kicker">The journal · {len(posts)} articles</p><h1>{e(title)}</h1><p>{e(description)}</p></header>{topic_links()}{search}<div id="archive-content"><div class="latest-grid archive-grid">{''.join(card(p) for p in batch)}</div><nav class="pagination" aria-label="Article pages">{pages}</nav><p class="post-meta">Page {number} of {count}</p></div>'''
        crumb = [('Home', '/'), (title, base)]
        if number > 1:
            crumb.append((f'Page {number}', url))
        write(url, page(title + (f' · Page {number}' if number > 1 else ''), description, url, body,
                        [collection(title, url, batch), breadcrumbs(crumb)]))


def related(post, posts):
    tokens = set(re.findall(r'[a-z]{4,}', post['title'].lower())) - {'what', 'when', 'check', 'first', 'before', 'from', 'with', 'your', 'steps'}
    candidates = [p for p in posts if p['slug'] != post['slug'] and p['topic'] == post['topic']]
    return sorted(candidates, key=lambda p: len(tokens & set(re.findall(r'[a-z]{4,}', p['title'].lower()))), reverse=True)[:3]


def localize_links(source, current, ids):
    # Only contextual links to an existing English edition change; originals stay credited.
    def replace(match):
        slug = 'naver-' + match[1]
        return f'href="/blog/posts/{slug}/"' if slug in ids and slug != current else match[0]
    return re.sub(r'href="https://(?:blog|m\.blog)\.naver\.com/swchoi1994/(\d+)(?:\?[^"<>]*)?"', replace, source)


def chrome(source):
    source = re.sub(r'<a class="skip-link".*?</header>', navigation(), source, count=1, flags=re.S)
    source = re.sub(r'<footer class="journal-footer">.*?</footer>\s*(?:<script[^>]*src=[^>]*></script>\s*)*', footer(), source, count=1, flags=re.S)
    source = source.replace('<body class="journal">', '<body class="journal publication">')
    source = source.replace('</head>', '<link rel="stylesheet" href="/assets/css/publication.css"></head>')
    return source


def article(post, posts):
    source = chrome(localize_links(post['source'], post['slug'], {p['slug'] for p in posts}))
    old = e(post['schema']['headline'])
    source = source.replace(old, e(post['title']))
    name = TOPICS[post['topic']][0]
    source = source.replace('<p class="kicker">AI · Software · Technology</p>', f'<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true"> / </span><a href="/topics/{post["topic"]}/">{name}</a></nav>')
    source = source.replace('<p class="article-summary">', '<p class="article-summary"><strong>At a glance</strong>')
    # Text-summary illustrations repeat the answer; keep them available below a disclosure.
    source = re.sub(r'(<figure>.*?/blog/media/en/.*?</figure>)', r'<details class="article-illustration"><summary>View the illustrated overview</summary>\1</details>', source, count=1, flags=re.S)
    recommendations = '<section class="related-media next-reading">' + heading('Keep exploring', 'A useful next read', f'/topics/{post["topic"]}/', 'More on this topic') + '<div class="story-grid">' + ''.join(card(p) for p in related(post, posts)) + '</div></section>'
    source, replaced = re.subn(r'<section class="related-media">\s*<h2>Related articles</h2>.*?</section>', lambda _: recommendations, source, flags=re.S)
    if not replaced:
        boundary = '</div></article></main>'
        if boundary not in source:
            raise ValueError(f'Article layout changed: {post["slug"]}')
        source = source.replace(boundary, recommendations + boundary, 1)
    data = dict(post['schema'])
    data.update(headline=post['title'], articleSection=name)
    for key in ('author', 'publisher'):
        data[key] = {'@type': 'Person', '@id': SITE + '/#person', 'name': NAME, 'url': SITE + '/blog/about/'}
    data['isPartOf']['url'] = SITE + '/'
    data['isPartOf']['name'] = BRAND
    crumb = breadcrumbs([('Home', '/'), (name, f'/topics/{post["topic"]}/'), (post['title'], post['url'])])
    source = LD.sub('', source)
    source = source.replace('</head>', structured(data) + structured(crumb) + '</head>')
    write(post['url'], source)


def build():
    posts = load_articles()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in ['assets', 'blog', 'guides', 'portfolio', 'openclaw-setup']:
        shutil.copytree(ROOT / name, OUT / name, ignore=shutil.ignore_patterns('.DS_Store', '__pycache__'))
    for path in ROOT.iterdir():
        if path.is_file() and (path.suffix in ('.txt', '.ico', '.xml') or path.name == '.nojekyll'):
            shutil.copy2(path, OUT / path.name)
    source = (ROOT / 'blog/index.html').read_text()
    media = re.findall(r'<article class="media-item">.*?</article>', source, re.S)
    if not media:
        raise ValueError('Upstream media format changed; review extraction before publishing')
    home(posts, media)
    archive(posts)
    for slug, (name, description) in TOPICS.items():
        archive([p for p in posts if p['topic'] == slug], f'/topics/{slug}/', name, description)
    body = '<header class="listing-intro"><p class="kicker">Choose your next read</p><h1>What can we help with?</h1><p>Practical guides, organized around what you want to do.</p></header><div class="topic-directory">'
    for slug, (name, description) in TOPICS.items():
        members = [p for p in posts if p['topic'] == slug]
        starter = next((p for p in members if p['slug'] in PICKS + STARTERS), members[0])
        body += f'<section><p class="post-meta">{len(members)} articles</p><h2><a href="/topics/{slug}/">{name} ↗</a></h2><p>{description}</p><p class="topic-starter">Start here: <a href="{starter["url"]}">{e(starter["title"])}</a></p></section>'
    write('/topics/', page('Browse by topic', 'Find guides to AI, Windows, Google tools, Office, privacy and backup.', '/topics/', body + '</div>', [breadcrumbs([('Home', '/'), ('Topics', '/topics/')])]))
    guide_posts = [next(p for p in posts if p['slug'] == slug) for slug in STARTERS + PICKS]
    body = '<header class="listing-intro"><p class="kicker">Learn something useful</p><h1>Guides worth keeping.</h1><p>A selected starting point for better tools, safer habits, and practical AI workflows.</p></header><section class="guide-spotlight"><p class="kicker">For builders</p><h2><a href="/guides/ai-coding-agent-repos/">AI coding agent repositories ↗</a></h2><p>Compare agent tools, skills, and plugins using dated GitHub data and clear installation checks.</p></section><div class="latest-grid archive-grid">' + ''.join(card(p) for p in guide_posts) + '</div>'
    write('/guides/', page('Practical technology guides', 'Selected guides to AI workflows, email, security, backups and coding agents.', '/guides/', body, [collection('Selected guides', '/guides/', guide_posts)]))
    write('/videos/', page('Videos & social posts', 'Technology stories from AI2Now on YouTube and Instagram.', '/videos/', '<header class="listing-intro"><p class="kicker">AI2Now</p><h1>Watch. Think. Explore.</h1><p>Published videos and social posts from the same creator behind the journal. YouTube players load only when you choose to watch.</p></header><div class="media-list">' + ''.join(media) + '</div>'))
    for post in posts:
        article(post, posts)
    affiliate_config = load_affiliates(ROOT / 'content/affiliates.json', {p['slug'] for p in posts})
    for post in posts:
        path = OUT / post['url'].lstrip('/') / 'index.html'
        path.write_text(apply_affiliates(path.read_text(), post['slug'], affiliate_config))
    for path in (OUT / 'blog').glob('*/index.html'):
        source = chrome(path.read_text())
        if path.parent.name == 'about':
            source = source.replace('href="/">portfolio', 'href="/portfolio/">portfolio')
            source = source.replace('<div class="reading-body">', '<div class="reading-body"><h2>About the author</h2><p>I’m Seongwoo Choi, an AI engineer and founder based in Abu Dhabi. My work spans agentic systems, multimodal document intelligence, and product delivery. <a href="/portfolio/">Read my professional background and research</a>.</p><h2>About the journal</h2>', 1)
            person = json.loads(LD.search((ROOT / 'portfolio/index.html').read_text())[1])
            person['url'] = SITE + '/blog/about/'
            source = source.replace('</head>', structured({'@context': 'https://schema.org', '@type': 'ProfilePage', 'url': SITE + '/blog/about/', 'mainEntity': person}) + '</head>')
        if path.parent.name == 'contact':
            source = source.replace('</div></article>', '<h2>Partnerships &amp; project inquiries</h2><p>For sponsorship or AI project inquiries, email <a href="mailto:swchoi1994@gmail.com?subject=Journal%20partnership%20inquiry">swchoi1994@gmail.com</a> with your organization, proposal, and timeline. Sponsorship does not purchase editorial recommendations; any sponsored material is clearly labeled.</p></div></article>')
        path.write_text(source)
    for path in (OUT / 'guides').glob('*/index.html'):
        source = chrome(path.read_text()).replace('"url": "https://swchoi1994.github.io/"', '"url": "https://swchoi1994.github.io/blog/about/"')
        path.write_text(source)
    portfolio = OUT / 'portfolio/index.html'
    source = portfolio.read_text().replace('<a class="nav-link" href="/blog/">Blog</a>', '<a class="nav-link" href="/">Journal</a>')
    portfolio.write_text(source)
    setup = OUT / 'openclaw-setup/index.html'
    source = setup.read_text()
    if 'rel="canonical"' not in source:
        source = source.replace('</head>', f'<link rel="canonical" href="{SITE}/openclaw-setup/"></head>')
    setup.write_text(source)
    add_analytics()
    search = [{k: p[k] for k in ('title', 'description', 'url', 'date', 'topic', 'minutes')} for p in posts]
    (OUT / 'blog/search-index.json').write_text(json.dumps(search, ensure_ascii=False))
    # Refresh feed titles alongside the visible headings; preserve publication dates and GUIDs.
    feed_path = OUT / 'blog/feed.xml'
    feed = ET.parse(feed_path)
    titles = {SITE + p['url']: p['title'] for p in posts}
    for item in feed.findall('./channel/item'):
        if item.findtext('link') in titles:
            item.find('title').text = titles[item.findtext('link')]
    feed.write(feed_path, encoding='utf-8', xml_declaration=True)
    # One complete sitemap, including every paginated archive and existing guide URL.
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', ns)
    sitemap = ET.Element(f'{{{ns}}}urlset')
    for path in sorted(OUT.rglob('index.html')):
        url = '/' + path.parent.relative_to(OUT).as_posix().strip('.')
        url = url.rstrip('/') + '/'
        entry = ET.SubElement(sitemap, f'{{{ns}}}url')
        ET.SubElement(entry, f'{{{ns}}}loc').text = SITE + url
    ET.ElementTree(sitemap).write(OUT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    print(f'Built {len(posts)} articles, {len(TOPICS)} topic collections and publication pages in {OUT}')


if __name__ == '__main__':
    build()
