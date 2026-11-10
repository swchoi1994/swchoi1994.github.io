#!/usr/bin/env python3
"""Render the publication around upstream-synced HTML; never modify sync inputs."""
import collections
import hashlib
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
TAGLINE = 'Practical guides to AI, everyday software, and safer digital habits. Clear steps, original sources.'
ADSENSE = 'ca-pub-5340843733211852'
PAGE_SIZE = 12
SOCIAL = {'src': '/assets/img/og-default.png', 'width': 1200, 'height': 630}
AVATAR = '/assets/img/avatar-96.webp'
YOUTUBE = 'https://www.youtube.com/@schoi1994'
X_PROFILE = 'https://x.com/swchoi1994'
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
ARROW = '<span aria-hidden="true">↗</span>'
ICONS = {
    'search': '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    'moon': '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
    'grid': '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    'list': '<path d="M4 6h16M4 12h16M4 18h16"/>',
}
# Filled in by build(); read by the shared page shell.
COUNTS = {}
SKIPPED = []


def content(name, default):
    """Owner-maintained settings under content/; a missing file means the feature is off."""
    path = ROOT / 'content' / name
    return json.loads(path.read_text()) if path.is_file() else default


CONFIG = content('site.json', {})


def structured(value):
    return '<script type="application/ld+json">' + json.dumps(value, ensure_ascii=False).replace('<', '\\u003c') + '</script>'


def icon(name, size=16):
    return f'<svg class="icon" aria-hidden="true" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'


def asset(path):
    """Version local CSS/JS by content so a deploy is never served from a stale cache."""
    return f'{path}?v={hashlib.sha256((ROOT / path.lstrip("/")).read_bytes()).hexdigest()[:10]}'


def topic_for(title):
    text = title.lower()
    if re.search(r'backup|bitlocker|passkey|2-step|personal information|privacy|permissions|quarantin|isolated files|quick assist|firewall|chatgpt memory|delete gemini|delete chatgpt|signed in to your google account|browser profiles', text):
        return 'privacy-backup'
    if re.search(r'gmail|google (drive|calendar|docs|storage)', text):
        return 'google-tools'
    if re.search(r'excel|\bword\b|powerpoint|pdf|ocr|scanning documents', text) and not re.search(r'\bai\b|chatgpt', text):
        return 'office-documents'
    if re.search(r'windows|laptop|bluetooth|wi-fi|monitor|task manager|battery|volume mixer|microphone|off-screen|video meeting|photos to a pc', text) and not re.search(r'ollama|rtx spark', text):
        return 'windows'
    return 'ai-automation'


def naver_only(slug, schema, source):
    """Korea-specific posts (tax, welfare, housing) belong on the Naver blog, not the English site.

    They are recognised by their sources: Korean government and public-institution domains.
    content/site.json can force a post either way with "posts" and "keep".
    """
    rule = CONFIG.get('naver_only', {})
    if slug in rule.get('keep', []):
        return False
    if slug in rule.get('posts', []):
        return True
    links = [u for u in schema.get('citation') or [] if isinstance(u, str)]
    box = re.search(r'<section class="source-box">(.*?)</section>', source, re.S)
    links += re.findall(r'href="(https?://[^"]+)"', box[1]) if box else []
    hosts = {urlsplit(u).netloc.lower() for u in links}
    for domain in rule.get('source_domains', []):
        bare = domain.lstrip('.')
        if any(host == bare or host.endswith('.' + bare) for host in hosts):
            return True
    return False


def load_articles():
    images = json.loads((ROOT / 'content/article-images.json').read_text())
    posts = []
    SKIPPED.clear()
    for path in sorted((ROOT / 'blog/posts').glob('*/index.html')):
        source = path.read_text()
        schemas = [json.loads(m[1]) for m in LD.finditer(source)]
        data = next(d for d in schemas if d.get('@type') == 'BlogPosting')
        slug = path.parent.name
        if naver_only(slug, data, source):
            SKIPPED.append((slug, data['headline']))
            continue
        title = TITLES.get(slug, data['headline'])
        illustration = images.get(slug, {
            'src': f'/blog/media/en/{slug}.svg', 'alt': f'Illustrated overview: {title}',
            'width': 1400, 'height': 1050,
            'credit': 'Explanatory illustration based on this article; not a product screenshot.',
        })
        if not (ROOT / illustration['src'].lstrip('/')).is_file():
            raise ValueError(f'Missing article image: {slug}')
        posts.append(dict(slug=slug, title=title, description=data['description'],
                          date=data['datePublished'], url=f'/blog/posts/{slug}/',
                          topic=topic_for(data['headline']),
                          minutes=max(1, math.ceil(data.get('wordCount', 600) / 220)),
                          source=source, schema=data, image=illustration))
    if not posts:
        raise ValueError('No published articles found; refusing to publish an empty site')
    return sorted(posts, key=lambda p: (p['date'], p['slug']), reverse=True)


def clip(text, limit=158):
    """A meta description that fits a search result without ending mid-word."""
    text = ' '.join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind('. '), cut.rfind('; '))
    if stop >= limit * 0.55:
        return cut[:stop + 1].rstrip(';') if cut[stop] == ';' else cut[:stop + 1]
    return cut[:cut.rfind(' ')].rstrip(',;:—-') + '…'


def short_title(title, limit=60):
    """Search results cut titles near 60 characters; keep the clause that names the subject."""
    if len(title) <= limit:
        return title
    heads = [title.split(mark, 1)[0] + ('?' if mark == '? ' else '') for mark in (': ', '? ', '; ', ' — ') if mark in title]
    heads = [head for head in heads if len(head) >= 20]
    fitting = [head for head in heads if len(head) <= limit]
    return fitting[0] if fitting else min(heads, key=len, default=title)


def document_title(title):
    title = short_title(title)
    for suffix in (' | Seongwoo Choi Journal', ' | Seongwoo Choi'):
        if len(title + suffix) <= 60:
            return title + suffix
    return title


def social_image(post):
    """Social scrapers and rich results need a raster image; SVG guides fall back to the site card."""
    image = post['image']
    return SOCIAL if image['src'].endswith('.svg') else image


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
# Runs before first paint so a saved or system dark preference never flashes light.
THEME = '''<script>(function(){try{var t=localStorage.getItem('theme');if(t!=='dark'&&t!=='light')t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.dataset.theme=t}catch(e){}})()</script>'''


def add_analytics():
    """Put the GA4 tag in the <head> of every published page except the OpenClaw setup tool."""
    for path in OUT.rglob('*.html'):
        if path.relative_to(OUT).parts[0] == 'openclaw-setup':
            continue
        source = path.read_text()
        if 'G-BLKN59SYTQ' not in source:
            assert source.count('</head>') == 1, path
            path.write_text(source.replace('</head>', ANALYTICS + '\n</head>'))


def sidebar(active, url):
    def link(href, label, extra=''):
        current = ' aria-current="page"' if href == url else ' aria-current="true"' if href == active else ''
        return f'<a href="{href}"{current}><span>{label}</span>{extra}</a>'
    out = f'<span class="out">{ARROW}</span>'
    topics = ''.join(link(f'/topics/{slug}/', e(name), f'<span class="count">{COUNTS.get(slug, 0)}</span>') for slug, (name, _) in TOPICS.items())
    return f'''<aside class="sidebar" id="sidebar">
<a class="brand" href="/">Seongwoo Choi<span> / Journal</span></a>
<a class="author-card" href="/blog/about/"><img src="{AVATAR}" width="38" height="38" alt=""><span><strong>Seongwoo Choi</strong><span>AI engineer &amp; founder</span></span></a>
<nav aria-label="Read"><p class="nav-label">Read</p>{link('/', 'Home')}{link('/blog/', 'All articles')}{link('/guides/', 'Guides')}{link('/videos/', 'Videos')}</nav>
<nav aria-label="Topics"><p class="nav-label">Topics</p>{topics}</nav>
<nav aria-label="Elsewhere"><p class="nav-label">Elsewhere</p><a href="{YOUTUBE}"><span>YouTube</span>{out}</a><a href="{X_PROFILE}"><span>X</span>{out}</a><a href="https://blog.naver.com/swchoi1994"><span>Naver · 한국어</span>{out}</a><a href="/blog/feed.xml"><span>RSS feed</span>{out}</a></nav>
<p class="sidebar-foot"><a href="/blog/about/">About</a> · <a href="/portfolio/">Portfolio &amp; CV</a> · <a href="/blog/contact/">Contact</a></p>
</aside>'''


def topic_tabs(url):
    """Phones have no sidebar, so listing pages carry the topics as a scrolling row."""
    def tab(href, label):
        return f'<a href="{href}"' + (' aria-current="page"' if href == url else '') + f'>{label}</a>'
    return '<nav class="topic-tabs" aria-label="Topics">' + tab('/', 'All') + ''.join(tab(f'/topics/{slug}/', e(name)) for slug, (name, _) in TOPICS.items()) + '</nav>'


def theme_toggle():
    return f'<button type="button" class="theme-toggle" data-theme-toggle aria-pressed="false">{icon("moon")}<span>Dark mode</span></button>'


def page_head(left):
    return f'<div class="page-head"><div class="page-title">{left}</div>{theme_toggle()}</div>'


def ad(slot):
    """A fixed ad unit. Renders only once the owner adds that unit's ID to content/site.json."""
    unit = CONFIG.get('ads', {}).get(slot, '')
    if not unit:
        return ''
    return f'<aside class="ad ad-{slot.replace("_", "-")}" aria-label="Advertisement"><p class="ad-label">Advertisement</p><ins class="adsbygoogle" style="display:block" data-ad-client="{ADSENSE}" data-ad-slot="{e(unit)}" data-ad-format="auto" data-full-width-responsive="true"></ins></aside>'


AD_NOTE = '''<aside class="ad-note" id="ad-note" aria-label="Ad blocker notice" hidden><p><strong>Ads look blocked on this page.</strong> They are what pays for the journal. If it helps you, please allow ads for this site.</p><div><button type="button" class="button button-primary" data-ad-note-help aria-expanded="false" aria-controls="ad-note-help">How to allow ads</button><button type="button" class="button" data-ad-note-close>Not now</button></div><p id="ad-note-help" hidden>Open your ad blocker’s menu while on this page, choose the option to pause it or not run on this site, then reload. In Brave, use the Shields icon in the address bar.</p></aside>'''


def footer():
    return f'''<footer class="site-footer"><p>© Seongwoo Choi. Advertising helps support this independent publication.</p><nav aria-label="Site information"><a href="/blog/about/">About</a><a href="/portfolio/">Portfolio &amp; CV</a><a href="/blog/contact/">Contact &amp; partnerships</a><a href="/blog/editorial/">Editorial policy</a><a href="/blog/privacy/">Privacy</a><a href="/blog/feed.xml">RSS</a><a href="https://blog.naver.com/swchoi1994">한국어 · Naver {ARROW}</a></nav></footer>'''


def page(title, description, url, body, schemas=(), *, active=None, rail='', kind='website', image=None,
         doc_title=None, head='', tabs=False, article_dates=None):
    image = image or SOCIAL
    alt = e(image.get('alt', BRAND))
    dates = ''.join(f'<meta property="article:{key}_time" content="{e(value)}">' for key, value in (article_dates or {}).items())
    rail = rail or ad('rail')
    rail_class = 'page-rail' if kind == 'article' else 'page-rail page-rail-wide'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(doc_title or document_title(title))}</title><meta name="description" content="{e(clip(description))}">
<link rel="canonical" href="{SITE}{url}"><meta name="robots" content="index,follow,max-image-preview:large"><meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f4f5f7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#15171b" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="{kind}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(clip(description, 200))}"><meta property="og:url" content="{SITE}{url}"><meta property="og:site_name" content="{BRAND}"><meta property="og:locale" content="en_US">
<meta property="og:image" content="{SITE}{e(image['src'])}"><meta property="og:image:width" content="{image['width']}"><meta property="og:image:height" content="{image['height']}"><meta property="og:image:alt" content="{alt}">{dates}
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(clip(description, 200))}"><meta name="twitter:image" content="{SITE}{e(image['src'])}">
{THEME}
<link rel="icon" href="/favicon.ico"><link rel="alternate" type="application/rss+xml" title="{BRAND}" href="/blog/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=JetBrains+Mono:wght@400;500&amp;display=swap" rel="stylesheet">
<link rel="stylesheet" href="{asset('/assets/css/journal.css')}">{head}
<meta name="google-adsense-account" content="{ADSENSE}"><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE}" crossorigin="anonymous" onerror="window.adsBlocked=true"></script>
{''.join(structured(s) for s in schemas)}</head><body><a class="skip-link" href="#main-content">Skip to content</a>
<div class="app">
<header class="topbar"><a class="brand" href="/">Seongwoo Choi<span> / Journal</span></a><div class="topbar-actions"><button type="button" class="icon-button" data-theme-toggle aria-pressed="false" aria-label="Dark mode">{icon('moon', 20)}</button><button type="button" class="icon-button" id="menu-toggle" aria-expanded="false" aria-controls="sidebar" aria-label="Open menu">{icon('menu', 20)}</button></div></header>
{sidebar(active or url, url)}
{topic_tabs(url) if tabs else ''}
<div class="page{' page-article' if kind == 'article' else ''}"><div class="page-main"><main id="main-content">{AD_NOTE}{body}</main>{ad('footer')}{footer()}</div>{f'<aside class="{rail_class}" aria-label="Beside the page">{rail}</aside>' if rail else ''}</div>
</div>
<script src="{asset('/assets/js/journal.js')}" defer></script></body></html>'''


def write(url, text):
    path = OUT / url.lstrip('/') / 'index.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def meta(post):
    return f'<p class="post-meta"><time datetime="{e(post["date"])}">{post["date"][:10]}</time> · {post["minutes"]} min read</p>'


def card(post, label=None, level=3):
    """One post. The same markup serves the card grid and the list; CSS decides the layout."""
    name = TOPICS[post['topic']][0]
    tag = f'<span class="post-label">{e(label)}</span>' if label else f'<a class="post-label" href="/topics/{post["topic"]}/">{e(name)}</a>'
    return f'<article class="post">{tag}<h{level}><a href="{post["url"]}">{e(post["title"])}</a></h{level}><p class="post-desc">{e(post["description"])}</p>{meta(post)}</article>'


def view_toggle():
    return f'<div class="view-toggle" role="group" aria-label="Layout"><button type="button" data-view-set="cards" aria-pressed="true">{icon("grid", 15)}Cards</button><button type="button" data-view-set="list" aria-pressed="false">{icon("list", 15)}List</button></div>'


def search_form(count, live=False):
    ident = ' id="archive-search"' if live else ''
    field = f'<label class="search-field">{icon("search", 18)}<span class="sr-only">Search articles</span><input type="search" name="q"{ident} placeholder="Search {count} articles" autocomplete="off"></label>'
    if not live:
        return f'<form class="search" role="search" action="/blog/" method="get">{field}</form>'
    return f'<form class="search" id="search" role="search" action="/blog/" method="get">{field}<noscript><p>Search requires JavaScript. All articles are available through the topics and numbered archive pages below.</p></noscript></form><p id="search-status" role="status" aria-live="polite"></p><div id="search-results" class="posts" data-view="list" hidden></div>'


def picture(post, eager=False):
    image = post['image']
    responsive = f' srcset="{e(image["small"])} 640w, {e(image["src"])} 1200w" sizes="(max-width: 760px) calc(100vw - 40px), 640px"' if image.get('small') else ''
    return f'<img src="{e(image["src"])}"{responsive} width="{image["width"]}" height="{image["height"]}" alt="{e(image["alt"])}" loading="{"eager" if eager else "lazy"}" decoding="async"' + (' fetchpriority="high"' if eager else '') + '>'


def youtube_videos(media):
    """Long-form uploads from the synced AI2Now media list, newest first."""
    videos = []
    for item in media:
        found = re.search(r'href="https://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})"', item)
        title = re.search(r'<h3>(.*?)</h3>', item, re.S)
        date = re.search(r'<p class="post-meta">[^<]*?(\d{4})\.(\d{2})\.(\d{2})</p>', item)
        if found and title:
            videos.append(dict(id=found[1], title=title[1].strip(), date='-'.join(date.groups()) if date else ''))
    return videos


def video_tile(video):
    date = f'<time datetime="{video["date"]}">{video["date"]}</time>' if video['date'] else ''
    return f'<a class="video" href="https://www.youtube.com/watch?v={video["id"]}"><span class="video-thumb"><img src="https://i.ytimg.com/vi/{video["id"]}/mqdefault.jpg" width="320" height="180" alt="" loading="lazy" decoding="async"></span><span class="video-title">{video["title"]}</span>{date}</a>'


def x_posts():
    posts = content('x-posts.json', [])
    if not posts:
        return ''
    items = ''
    for post in posts[:3]:
        link = f' <a href="{e(post["link_url"])}">{e(post["link_label"])}</a>' if post.get('link_url') else ''
        items += f'<article class="x-post"><p>{e(post["text"])}{link}</p><a class="x-date" href="{e(post["url"])}"><time datetime="{e(post["date"])}">{e(post["date"])}</time><span class="sr-only"> on X</span></a></article>'
    return f'<section class="block card" aria-labelledby="x-title"><div class="block-head"><h2 id="x-title">On X</h2><a class="more" href="{X_PROFILE}">@swchoi1994 {ARROW}</a></div><div class="x-posts">{items}</div></section>'


def home(posts, media):
    by_id = {p['slug']: p for p in posts}
    groups = [(name, [by_id[s] for s in ids]) for name, ids in AI_PICKS]
    chosen = [p for _, members in groups for p in members]
    featured = ''.join(card(p, label=name) for name, members in groups for p in members)
    latest = ''.join(card(p) for p in posts[:6])
    videos = ''.join(video_tile(v) for v in youtube_videos(media)[:4])
    body = f'''{page_head(f'<p class="eyebrow">Journal</p><h1>Make technology work for you.</h1><p class="lede">{TAGLINE}</p>')}
{search_form(len(posts))}
<section class="block" aria-labelledby="featured-title"><div class="block-head"><h2 id="featured-title">Featured guides <span class="note">Chosen by hand, not by traffic</span></h2>{view_toggle()}</div><div class="posts" data-view="cards" data-switchable>{featured}</div></section>
<section class="block" aria-labelledby="latest-title"><div class="block-head"><h2 id="latest-title">Latest articles</h2><a class="more" href="/blog/">Browse all {len(posts)} articles →</a></div><div class="posts" data-view="list">{latest}</div></section>
{ad('between')}
<section class="block card" id="videos" aria-labelledby="videos-title"><div class="block-head"><h2 id="videos-title">Latest videos <span class="note">AI2Now on YouTube</span></h2><a class="more" href="/videos/">All videos &amp; posts →</a></div><div class="videos">{videos}</div><p class="block-foot"><a href="{YOUTUBE}">Open the channel {ARROW}</a></p></section>
{x_posts()}
<section class="block card guide-spotlight"><p class="eyebrow">For builders</p><h2><a href="/guides/ai-coding-agent-repos/">Find your next AI coding tool</a></h2><p>A guide to agent repositories, skills, and plugins, with dated GitHub star counts and things to check before installing.</p></section>'''
    person = json.loads(LD.search((ROOT / 'portfolio/index.html').read_text())[1])
    person['url'] = SITE + '/blog/about/'
    schemas = [{'@context': 'https://schema.org', '@type': 'WebSite', '@id': SITE + '/#website', 'url': SITE + '/', 'name': BRAND, 'inLanguage': 'en', 'publisher': {'@id': SITE + '/#person'},
                'potentialAction': {'@type': 'SearchAction', 'target': {'@type': 'EntryPoint', 'urlTemplate': SITE + '/blog/?q={search_term_string}'}, 'query-input': 'required name=search_term_string'}}, person,
               {'@context': 'https://schema.org', '@type': 'Blog', '@id': SITE + '/blog/#blog', 'url': SITE + '/', 'name': BRAND, 'author': {'@id': SITE + '/#person'}},
               collection('Featured guides: selected AI articles', '/', chosen)]
    write('/', page('Practical AI & technology guides', 'Practical guides to AI, Windows, Google tools, documents, privacy and backup. By AI engineer Seongwoo Choi.', '/', body, schemas,
                    doc_title='Practical AI & technology guides | Seongwoo Choi Journal', tabs=True))


def archive(posts, base='/blog/', title='All articles', description='Find a useful answer. Browse the latest guides, or search the complete journal.', eyebrow='The journal'):
    count = math.ceil(len(posts) / PAGE_SIZE)
    for number in range(1, count + 1):
        def address(i):
            return base if i == 1 else f'{base}page/{i}/'
        url = address(number)
        batch = posts[(number - 1) * PAGE_SIZE:number * PAGE_SIZE]
        search = search_form(len(posts), live=True) if base == '/blog/' else ''
        numbers = ''.join(f'<a href="{address(i)}"' + (' aria-current="page"' if i == number else '') + f' aria-label="Page {i}">{i}</a>' for i in range(1, count + 1))
        older = f'<a class="step" rel="next" href="{address(number + 1)}">Older →</a>' if number < count else ''
        newer = f'<a class="step" rel="prev" href="{address(number - 1)}">← Newer</a>' if number > 1 else ''
        pages = f'<nav class="pagination" aria-label="Article pages">{newer}<span class="numbers">{numbers}</span>{older}</nav>' if count > 1 else ''
        head = (f'<link rel="prev" href="{SITE}{address(number - 1)}">' if number > 1 else '') + (f'<link rel="next" href="{SITE}{address(number + 1)}">' if number < count else '')
        body = f'''{page_head(f'<p class="eyebrow">{e(eyebrow)} · {len(posts)} articles</p><h1>{e(title)}</h1><p class="lede">{e(description)}</p>')}
{search}<div id="archive-content"><section class="block" aria-label="Articles"><div class="block-head"><p class="note">Page {number} of {count}</p>{view_toggle()}</div><div class="posts" data-view="cards" data-switchable>{''.join(card(p, level=2) for p in batch)}</div></section>{pages}</div>'''
        crumb = [('Home', '/'), (title, base)]
        if number > 1:
            crumb.append((f'Page {number}', url))
        paged = f' Page {number} of {count}.' if number > 1 else ''
        write(url, page(title + (f' · Page {number}' if number > 1 else ''), clip(description, 140) + paged, url, body,
                        [collection(title, url, batch), breadcrumbs(crumb)], active=base, head=head, tabs=True))


TOKEN_STOP = {'what', 'when', 'check', 'first', 'before', 'from', 'with', 'your', 'steps', 'that', 'this', 'how', 'the', 'and', 'for', 'into', 'order', 'using', 'should', 'after', 'does', 'are', 'can', 'not'}


def tokens(title):
    return set(re.findall(r'[a-z0-9][a-z0-9+.-]{2,}', title.lower())) - TOKEN_STOP


def related(post, posts):
    """Three same-topic posts sharing the rarest title words; ties go to the newest."""
    frequency = collections.Counter(t for p in posts for t in tokens(p['title']))
    mine = tokens(post['title'])
    candidates = [p for p in posts if p['slug'] != post['slug'] and p['topic'] == post['topic']]
    return sorted(candidates, key=lambda p: sum(1 / frequency[t] for t in mine & tokens(p['title'])), reverse=True)[:3]


def localize_links(source, current, ids):
    # Only contextual links to an existing English edition change; originals stay credited.
    def replace(match):
        slug = 'naver-' + match[1]
        return f'href="/blog/posts/{slug}/"' if slug in ids and slug != current else match[0]
    return re.sub(r'href="https://(?:blog|m\.blog)\.naver\.com/swchoi1994/(\d+)(?:\?[^"<>]*)?"', replace, source)


def numbered_steps(body):
    """Turn runs of paragraphs that start ①, ②, ③ into a real ordered list search engines can read."""
    def convert(match):
        items = re.findall(r'<p>([①-⑳])\s*(.*?)</p>', match[0], re.S)
        if [ord(mark) - 0x2460 for mark, _ in items] != list(range(len(items))):
            return match[0]
        return '<ol>' + ''.join(f'<li>{text}</li>' for _, text in items) + '</ol>'
    return re.sub(r'(?:<p>[①-⑳](?:(?!</?p\b).)*</p>\s*){2,}', convert, body, flags=re.S)


def named_sources(body):
    """Source lists arrive as bare URLs; reuse the descriptive link text the article already gives them."""
    box = re.search(r'<section class="source-box">.*?</section>', body, re.S)
    if not box:
        return body
    names = {}
    for href, text in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', body[:box.start()], re.S):
        label = re.sub(r'\s*<span aria-hidden="true">↗</span>', '', text).strip()
        if label and '<' not in label and not re.match(r'(https?://|www\.)|[\w.-]+\.[a-z]{2,}(/|$)', label):
            names.setdefault(href, label)

    def rename(match):
        label = names.get(match[1])
        return f'<li><a href="{match[1]}"{match[2]}>{label} {ARROW}</a></li>' if label else match[0]
    return body[:box.start()] + re.sub(r'<li><a href="([^"]+)"([^>]*)>.*?</a></li>', rename, box[0], flags=re.S) + body[box.end():]


def comments():
    """Reader comments through giscus (GitHub Discussions). Hidden until the owner fills in content/site.json."""
    c = CONFIG.get('comments', {})
    if not all(c.get(key) for key in ('repo', 'repo_id', 'category', 'category_id')):
        return ''
    data = ' '.join(f'data-{key.replace("_", "-")}="{e(c[key])}"' for key in ('repo', 'repo_id', 'category', 'category_id'))
    return f'<section class="block card comments" aria-labelledby="comments-title"><h2 id="comments-title">Comments</h2><p>Corrections and questions are welcome. Sign-in is through GitHub, and the comment box loads only when you open it.</p><button type="button" class="button button-primary" data-comments {data}>Show comments</button><div id="comments-thread"></div></section>'


def article(post, posts):
    slug = post['slug']
    source = localize_links(post['source'], slug, {p['slug'] for p in posts})
    found = re.search(r'<div class="reading-body">(.*)</div></article></main>', source, re.S)
    summary = re.search(r'<p class="article-summary">(.*?)</p>', source, re.S)
    if not found or not summary:
        raise ValueError(f'Article layout changed: {slug}')
    body = found[1]
    name = TOPICS[post['topic']][0]

    contents = re.search(r'<nav aria-label="In this article">.*?</nav>', body, re.S)
    sections = re.findall(r'<li><a href="#([^"]+)">(.*?)</a></li>', contents[0], re.S) if contents else []
    if contents:
        body = body.replace(contents[0], '', 1)
    media = ''
    for block in re.findall(r'<section class="related-media">.*?</section>', body, re.S):
        body = body.replace(block, '', 1)
        if '<h2>Related articles</h2>' not in block:
            media += block.replace('<section class="related-media">', '<section class="block card related-media">', 1)
    body = named_sources(numbered_steps(body))

    reference = post['image'].get('reference')
    if reference:
        if not (ROOT / reference['src'].lstrip('/')).is_file():
            raise ValueError(f'Missing reference image: {slug}')
        visual = f'<figure class="article-reference"><img src="{e(reference["src"])}" width="{reference["width"]}" height="{reference["height"]}" alt="{e(reference["alt"])}" loading="lazy" decoding="async"><figcaption>{e(reference["caption"])} <a href="{e(reference["source_url"])}">Source: Microsoft Support</a>. {e(reference["credit"])} <a href="{e(reference["permission_url"])}">Reuse terms</a>.</figcaption></figure>'
        boundary = '<section class="source-box">'
        if body.count(boundary) != 1:
            raise ValueError(f'Article source section changed: {slug}')
        body = body.replace(boundary, visual + boundary, 1)

    links = ''.join(f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in sections)
    inline_contents = f'<details class="toc-inline"><summary>In this article <span>{len(sections)} sections</span></summary><ol>{links}</ol></details>' if sections else ''
    extra = content('post-meta.json', {}).get(slug, {})
    mood = ''.join(f'<div><dt>{key}</dt><dd>{e(extra[key])}</dd></div>' for key in ('mood', 'music') if extra.get(key))
    cover = f'<figure class="article-cover">{picture(post, True)}<figcaption>{e(post["image"]["credit"])}</figcaption></figure>' if CONFIG.get('article_cover') else ''
    header = f'''<header class="reading-header"><h1>{e(post['title'])}</h1><p class="byline"><img src="{AVATAR}" width="28" height="28" alt=""><a rel="author" href="/blog/about/">{NAME}</a><span><time datetime="{e(post['date'])}">{post['date'][:10]}</time> · {post['minutes']} min read</span></p>{f'<dl class="mood">{mood}</dl>' if mood else ''}<p class="article-summary"><strong>At a glance</strong>{summary[1]}</p></header>'''
    picks = ''.join(card(p) for p in related(post, posts))
    reading = f'''{page_head(f'<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true"> / </span><a href="/topics/{post["topic"]}/">{e(name)}</a></nav>')}
<article class="reading card">{header}{cover}<div class="reading-body">{inline_contents}{body}</div></article>
{ad('article_end')}{comments()}
<section class="block next-reading" aria-labelledby="next-title"><div class="block-head"><h2 id="next-title">Keep reading</h2><a class="more" href="/topics/{post['topic']}/">More on this topic →</a></div><div class="posts" data-view="list">{picks}</div></section>{media}'''
    rail = (f'<nav class="toc card" aria-label="In this article"><p class="eyebrow">In this article</p><ol>{links}</ol></nav>' if sections else '') + ad('rail') + f'<section class="card author-box" aria-label="About the author"><p class="author-name"><img src="{AVATAR}" width="44" height="44" alt=""><span><strong>{NAME}</strong><span>AI engineer &amp; founder</span></span></p><p>I’m Seongwoo Choi, an AI engineer and founder based in Abu Dhabi. This journal brings together practical software guides and technology analysis.</p><p><a href="/blog/about/">About the author &amp; editorial approach →</a></p></section>'

    image = social_image(post)
    data = dict(post['schema'])
    data.update(headline=post['title'], articleSection=name, image=SITE + image['src'],
                dateModified=post['schema'].get('dateModified', post['date']))
    for key in ('author', 'publisher'):
        data[key] = {'@type': 'Person', '@id': SITE + '/#person', 'name': NAME, 'url': SITE + '/blog/about/'}
    data['isPartOf'] = dict(data['isPartOf'], url=SITE + '/', name=BRAND)
    # The Korean original is the source work; say so in a form crawlers can read.
    data['isBasedOn'] = {'@type': 'BlogPosting', 'inLanguage': 'ko', 'url': f'https://blog.naver.com/swchoi1994/{slug.split("-")[1]}'}
    crumb = breadcrumbs([('Home', '/'), (name, f'/topics/{post["topic"]}/'), (post['title'], post['url'])])
    write(post['url'], page(post['title'], post['description'], post['url'], reading, [data, crumb], active=f'/topics/{post["topic"]}/', rail=rail,
                            kind='article', image=dict(image, alt=post['image']['alt']),
                            article_dates={'published': post['date'], 'modified': data['dateModified']}))


def info_page(path, posts):
    """About, contact, editorial and privacy pages keep their upstream text inside the new shell."""
    source = path.read_text()
    found = re.search(r'<article class="reading info-page">(.*)</article></main>', source, re.S)
    description = re.search(r'<meta name="description" content="([^"]*)"', source)
    if not found or not description:
        raise ValueError(f'Information page layout changed: {path.parent.name}')
    inner = re.sub(r'<a href="/blog/" class="back-link">.*?</a>', '', found[1], count=1)
    title = html.unescape(re.sub(r'<[^>]+>', '', re.search(r'<h1>(.*?)</h1>', inner, re.S)[1]))
    schemas = []
    if path.parent.name == 'about':
        inner = inner.replace('href="/">portfolio', 'href="/portfolio/">portfolio')
        inner = inner.replace('<div class="reading-body">', '<div class="reading-body"><h2>About the author</h2><p>I’m Seongwoo Choi, an AI engineer and founder based in Abu Dhabi. My work spans agentic systems, multimodal document intelligence, and product delivery. <a href="/portfolio/">Read my professional background and research</a>.</p><h2>About the journal</h2>', 1)
        person = json.loads(LD.search((ROOT / 'portfolio/index.html').read_text())[1])
        person['url'] = SITE + '/blog/about/'
        schemas.append({'@context': 'https://schema.org', '@type': 'ProfilePage', 'url': SITE + '/blog/about/', 'mainEntity': person})
    if path.parent.name == 'contact':
        inner = re.sub(r'</div>\s*$', '<h2>Partnerships &amp; project inquiries</h2><p>For sponsorship or AI project inquiries, email <a href="mailto:swchoi1994@gmail.com?subject=Journal%20partnership%20inquiry">swchoi1994@gmail.com</a> with your organization, proposal, and timeline. Sponsorship does not purchase editorial recommendations; any sponsored material is clearly labeled.</p></div>', inner, count=1)
    url = f'/blog/{path.parent.name}/'
    crumbs = '<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a></nav>'
    write(url, page(title, html.unescape(description[1]), url, f'{page_head(crumbs)}<article class="reading info-page card">{inner}</article>', schemas))


def guide_page(path):
    """Hand-maintained guides under /guides/ keep their own content and metadata inside the new shell."""
    source = path.read_text()
    found = re.search(r'<article class="reading guide">(.*)</article>\s*</main>', source, re.S)
    title = re.search(r'<meta property="og:title" content="([^"]*)"', source)
    description = re.search(r'<meta name="description" content="([^"]*)"', source)
    picture_url = re.search(r'<meta property="og:image" content="([^"]*)"', source)
    if not (found and title and description):
        raise ValueError(f'Guide layout changed: {path.parent.name}')
    inner = re.sub(r'<a href="/blog/" class="back-link">.*?</a>', '', found[1], count=1)
    schemas = [json.loads(m[1].replace('"url": "https://swchoi1994.github.io/"', '"url": "https://swchoi1994.github.io/blog/about/"')) for m in LD.finditer(source)]
    image = {'src': urlsplit(picture_url[1]).path, 'width': 1200, 'height': 630} if picture_url else None
    url = f'/guides/{path.parent.name}/'
    crumbs = '<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true"> / </span><a href="/guides/">Guides</a></nav>'
    write(url, page(html.unescape(title[1]), html.unescape(description[1]), url, f'{page_head(crumbs)}<article class="reading guide card">{inner}</article>', schemas,
                    active='/guides/', kind='article', image=image))


def llms(posts):
    """A short map of the site for AI assistants; the same pages people read, nothing hidden."""
    by_id = {p['slug']: p for p in posts}
    lines = [f'# {BRAND}', '', f'> {TAGLINE} Written by AI engineer {NAME}. Articles are English editions of Korean originals and link their sources.', '', '## Topics']
    lines += [f'- [{name}]({SITE}/topics/{slug}/): {description}' for slug, (name, description) in TOPICS.items()]
    lines += ['', '## Featured guides']
    lines += [f'- [{by_id[s]["title"]}]({SITE}{by_id[s]["url"]}): {clip(by_id[s]["description"], 200)}' for _, ids in AI_PICKS for s in ids]
    lines += ['', '## More', f'- [All articles]({SITE}/blog/)', f'- [AI coding agent repositories guide]({SITE}/guides/ai-coding-agent-repos/)',
              f'- [About the author]({SITE}/blog/about/)', f'- [Editorial policy]({SITE}/blog/editorial/)', f'- [RSS feed]({SITE}/blog/feed.xml)', '']
    (OUT / 'llms.txt').write_text('\n'.join(lines))


def build():
    posts = load_articles()
    COUNTS.clear()
    COUNTS.update(collections.Counter(p['topic'] for p in posts))
    published = {p['slug'] for p in posts}
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in ['assets', 'blog', 'guides', 'portfolio', 'openclaw-setup']:
        shutil.copytree(ROOT / name, OUT / name, ignore=shutil.ignore_patterns('.DS_Store', '__pycache__'))
    if (ROOT / 'learning-media').is_dir():
        shutil.copytree(ROOT / 'learning-media', OUT / 'learning-media')
    for path in ROOT.iterdir():
        if path.is_file() and (path.suffix in ('.txt', '.ico', '.xml') or path.name == '.nojekyll'):
            shutil.copy2(path, OUT / path.name)
    # Posts kept for the Naver blog only must not ship in their raw upstream form either.
    for path in (OUT / 'blog/posts').iterdir():
        if path.name not in published:
            shutil.rmtree(path)
    source = (ROOT / 'blog/index.html').read_text()
    media = re.findall(r'<article class="media-item">.*?</article>', source, re.S)
    if not media:
        raise ValueError('Upstream media format changed; review extraction before publishing')
    home(posts, media)
    archive(posts)
    for slug, (name, description) in TOPICS.items():
        archive([p for p in posts if p['topic'] == slug], f'/topics/{slug}/', name, description, 'Topic')
    cards = ''
    for slug, (name, description) in TOPICS.items():
        members = [p for p in posts if p['topic'] == slug]
        starter = next((p for p in members if p['slug'] in PICKS + STARTERS), members[0])
        cards += f'<section class="post topic-card"><span class="post-label">{len(members)} articles</span><h2><a href="/topics/{slug}/">{e(name)}</a></h2><p class="post-desc">{e(description)}</p><p class="topic-starter">Start here: <a href="{starter["url"]}">{e(starter["title"])}</a></p></section>'
    body = page_head('<p class="eyebrow">Choose your next read</p><h1>What can we help with?</h1><p class="lede">Practical guides, organized around what you want to do.</p>') + f'<div class="posts topic-directory" data-view="cards">{cards}</div>'
    write('/topics/', page('Browse by topic', 'Find guides to AI, Windows, Google tools, Office, privacy and backup.', '/topics/', body, [breadcrumbs([('Home', '/'), ('Topics', '/topics/')])], tabs=True))
    guide_posts = [next(p for p in posts if p['slug'] == slug) for slug in STARTERS + PICKS]
    body = page_head('<p class="eyebrow">Learn something useful</p><h1>Guides worth keeping.</h1><p class="lede">A selected starting point for better tools, safer habits, and practical AI workflows.</p>') + '<section class="block card guide-spotlight"><p class="eyebrow">For builders</p><h2><a href="/guides/ai-coding-agent-repos/">AI coding agent repositories</a></h2><p>Compare agent tools, skills, and plugins using dated GitHub data and clear installation checks.</p></section><div class="posts" data-view="cards">' + ''.join(card(p, level=2) for p in guide_posts) + '</div>'
    write('/guides/', page('Practical technology guides', 'Selected guides to AI workflows, email, security, backups and coding agents.', '/guides/', body, [collection('Selected guides', '/guides/', guide_posts)]))
    body = page_head('<p class="eyebrow">AI2Now</p><h1>Watch. Think. Explore.</h1><p class="lede">Published videos and social posts from the same creator behind the journal. YouTube players load only when you choose to watch.</p>') + '<div class="media-list">' + ''.join(media) + '</div>'
    write('/videos/', page('Videos & social posts', 'Technology stories from AI2Now on YouTube and Instagram.', '/videos/', body))
    for post in posts:
        article(post, posts)
    affiliate_config = load_affiliates(ROOT / 'content/affiliates.json', published)
    for post in posts:
        path = OUT / post['url'].lstrip('/') / 'index.html'
        path.write_text(apply_affiliates(path.read_text(), post['slug'], affiliate_config))
    for path in sorted((ROOT / 'blog').glob('*/index.html')):
        info_page(path, posts)
    for path in sorted((ROOT / 'guides').glob('*/index.html')):
        guide_page(path)
    portfolio = OUT / 'portfolio/index.html'
    source = portfolio.read_text().replace('<a class="nav-link" href="/blog/">Blog</a>', '<a class="nav-link" href="/">Journal</a>')
    portfolio.write_text(source)
    setup = OUT / 'openclaw-setup/index.html'
    source = setup.read_text()
    if 'rel="canonical"' not in source:
        source = source.replace('</head>', f'<link rel="canonical" href="{SITE}/openclaw-setup/"></head>')
    setup.write_text(source)
    add_analytics()
    search = [dict({k: p[k] for k in ('title', 'description', 'url', 'minutes')}, date=p['date'][:10], topic=TOPICS[p['topic']][0], topic_url=f'/topics/{p["topic"]}/') for p in posts]
    (OUT / 'blog/search-index.json').write_text(json.dumps(search, ensure_ascii=False))
    llms(posts)
    # Refresh the upstream feed: current titles and site name, without the Naver-only posts.
    feed_path = OUT / 'blog/feed.xml'
    feed = ET.parse(feed_path)
    channel = feed.find('./channel')
    channel.find('title').text = BRAND
    titles = {SITE + p['url']: p['title'] for p in posts}
    for item in channel.findall('item'):
        link = item.findtext('link')
        if link in titles:
            item.find('title').text = titles[link]
        elif '/blog/posts/' in (link or ''):
            channel.remove(item)
    feed.write(feed_path, encoding='utf-8', xml_declaration=True)
    # One complete sitemap, including every paginated archive and existing guide URL.
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', ns)
    sitemap = ET.Element(f'{{{ns}}}urlset')
    dated = {p['url']: p['date'][:10] for p in posts}
    newest = posts[0]['date'][:10]
    for path in sorted(OUT.rglob('index.html')):
        url = '/' + path.parent.relative_to(OUT).as_posix().strip('.')
        url = url.rstrip('/') + '/'
        entry = ET.SubElement(sitemap, f'{{{ns}}}url')
        ET.SubElement(entry, f'{{{ns}}}loc').text = SITE + url
        # Posts change when published; listing pages change whenever a post is added.
        if url in dated or url == '/' or url.startswith(('/blog/page/', '/topics/')) or url == '/blog/':
            ET.SubElement(entry, f'{{{ns}}}lastmod').text = dated.get(url, newest)
    ET.ElementTree(sitemap).write(OUT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    print(f'Built {len(posts)} articles, {len(TOPICS)} topic collections and publication pages in {OUT}')
    if SKIPPED:
        print(f'Left {len(SKIPPED)} Naver-only articles off the English site: ' + ', '.join(slug for slug, _ in SKIPPED))


if __name__ == '__main__':
    build()
