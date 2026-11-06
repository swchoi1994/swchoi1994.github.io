#!/usr/bin/env python3
"""Build the hand-maintained guide pages under /guides/.

The blog sync job owns blog/, sitemap.xml and blog/feed.xml, so guides live
outside those paths and publish their own sitemap-guides.xml.

  python3 tools/guides.py fetch   # refresh GitHub star counts (adds a dated snapshot)
  python3 tools/guides.py build   # render HTML, sitemap and preview image
"""
import datetime as dt
import html
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://swchoi1994.github.io"
ADSENSE_CLIENT = "ca-pub-5340843733211852"
GUIDE_DIR = ROOT / "guides" / "ai-coding-agent-repos"
CHROME = os.environ.get("CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def github_token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def fetch():
    guide = load(GUIDE_DIR / "repos.json")
    stars_path = GUIDE_DIR / "stars.json"
    stars = load(stars_path) if stars_path.exists() else {"snapshots": {}}
    token = github_token()
    repos = {}
    for entry in guide["repos"]:
        req = urllib.request.Request(f"https://api.github.com/repos/{entry['repo']}")
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            info = json.load(resp)
        repos[entry["repo"]] = {
            "url": info["html_url"],
            "stars": info["stargazers_count"],
            "created": info["created_at"][:10],
            "pushed": info["pushed_at"][:10],
            "language": info.get("language"),
            "license": (info.get("license") or {}).get("spdx_id"),
        }
    now = dt.datetime.now(dt.timezone.utc)
    stars["fetched_at"] = now.isoformat(timespec="seconds")
    stars["repos"] = repos
    stars["snapshots"][now.date().isoformat()] = {name: r["stars"] for name, r in repos.items()}
    save(stars_path, stars)
    print(f"fetched {len(repos)} repos")


def weekly_gains(stars, today):
    """Calendar-date delta, only when a snapshot exactly seven days earlier exists."""
    baseline_date = (today - dt.timedelta(days=7)).isoformat()
    base = stars["snapshots"].get(baseline_date)
    if base is None:
        return None
    return {name: r["stars"] - base[name] for name, r in stars["repos"].items() if name in base}


def fmt(n):
    return f"{n:,}"


def head(title, description, url, image, json_ld):
    e = html.escape
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} | Seongwoo Choi</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#f6f4ef">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Seongwoo Choi IT Blog">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{image}">
<link rel="icon" href="/favicon.ico">
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="stylesheet" href="/blog/blog.css">
<link rel="stylesheet" href="/guides/guides.css">
<link rel="alternate" type="application/rss+xml" title="Seongwoo Choi IT Blog" href="/blog/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&amp;family=Newsreader:opsz,wght@6..72,500;6..72,600&amp;display=swap" rel="stylesheet">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-BLKN59SYTQ"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-BLKN59SYTQ');</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}" crossorigin="anonymous"></script>
<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
</head>"""


NAV = """<body class="journal">
<a class="skip-link" href="#main-content">Skip to content</a>
<header class="site-header"><nav class="site-nav" aria-label="Main navigation">
<a class="site-brand" href="/"><span>Seongwoo Choi</span><span class="site-brand__mark" aria-hidden="true">SC</span></a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav-menu" aria-label="Open menu"><span></span><span></span><span></span></button>
<div class="nav-menu" id="nav-menu"><a class="nav-link" href="/portfolio/">Portfolio</a><a class="nav-link" href="/blog/">Blog</a><a class="nav-link" href="/blog/#media">Videos &amp; posts</a><a class="nav-link" href="/blog/about/">About</a><a class="nav-link" href="/blog/contact/">Contact</a></div>
</nav></header>"""

FOOTER = """<footer class="journal-footer">
<div><strong>Seongwoo Choi</strong><p>AI and software changes, with context.</p></div>
<nav aria-label="Site information"><a href="/blog/about/">About</a><a href="/blog/editorial/">Editorial policy</a><a href="/blog/privacy/">Privacy policy</a><a href="/blog/contact/">Contact &amp; corrections</a><a href="/blog/feed.xml">RSS</a></nav>
<small>© {year} Seongwoo Choi</small>
</footer>
<script src="/assets/js/script.js" defer></script>
</body>
</html>
"""


def build_repo_guide():
    guide = load(GUIDE_DIR / "repos.json")
    stars = load(GUIDE_DIR / "stars.json")
    fetched = dt.datetime.fromisoformat(stars["fetched_at"])
    today = fetched.date()
    gains = weekly_gains(stars, today)
    url = f"{SITE}/guides/{guide['slug']}/"
    image = f"{url}og.png"
    month = fetched.strftime("%B %Y")
    title = f"{guide['title']} ({month})"
    updated = f"{fetched:%B} {fetched.day}, {fetched.year}"
    e = html.escape

    entries = sorted(guide["repos"], key=lambda r: stars["repos"][r["repo"]]["stars"], reverse=True)
    group_names = {g["id"]: g["name"] for g in guide["groups"]}

    def per_day(r):
        data = stars["repos"][r["repo"]]
        age = max(1, (today - dt.date.fromisoformat(data["created"])).days)
        return round(data["stars"] / age)

    rows = []
    for rank, r in enumerate(entries, 1):
        data = stars["repos"][r["repo"]]
        gain = f"<td>{gains[r['repo']]:+,}</td>" if gains and r["repo"] in gains else ("<td>–</td>" if gains else "")
        rows.append(
            f'<tr><td>{rank}</td><td><a href="#{e(r["repo"].replace("/", "-"))}">{e(r["name"])}</a></td>'
            f'<td class="col-group">{e(group_names[r["group"]])}</td><td>{fmt(data["stars"])}</td>{gain}'
            f'<td>{fmt(per_day(r))}</td></tr>'
        )
    gain_th = "<th scope=\"col\">7-day date delta</th>" if gains else ""

    sections = []
    for group in guide["groups"]:
        members = [r for r in entries if r["group"] == group["id"]]
        cards = []
        for r in members:
            data = stars["repos"][r["repo"]]
            meta = [f"{fmt(data['stars'])} stars", f"created {data['created']}", f"last push {data['pushed']}"]
            meta += [x for x in (data.get("language"), data.get("license")) if x and x != "NOASSERTION"]
            take = f'<p class="repo-take"><strong>From my own use:</strong> {e(r["take"])}</p>' if r["take"] else ""
            cards.append(
                f'<section class="repo-card" id="{e(r["repo"].replace("/", "-"))}">'
                f'<h3><a href="{data["url"]}" rel="noopener">{e(r["name"])}</a> <span class="repo-path">{e(r["repo"])}</span></h3>'
                f'<p class="post-meta">{" · ".join(e(m) for m in meta)}</p>'
                f'<p>{e(r["what"])}</p><p class="repo-check"><strong>Check first:</strong> {e(r["check"])}</p>{take}</section>'
            )
        video = ""
        if group.get("video"):
            v = group["video"]
            video = (
                f'<a class="video-card" href="https://www.youtube.com/watch?v={v["id"]}" rel="noopener">'
                f'<img src="https://i.ytimg.com/vi/{v["id"]}/hqdefault.jpg" alt="" loading="lazy" width="160" height="120">'
                f'<span>Video: {e(v["title"])}</span></a>'
            )
        sections.append(
            f'<h2 id="{group["id"]}">{e(group["name"])}</h2><p>{e(group["intro"])}</p>{video}{"".join(cards)}'
        )

    toc = "".join(f'<li><a href="#{g["id"]}">{e(g["name"])}</a></li>' for g in guide["groups"])
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": guide["description"],
        "url": url,
        "image": image,
        "datePublished": guide["published"],
        "dateModified": stars["fetched_at"],
        "inLanguage": "en",
        "author": {"@type": "Person", "@id": f"{SITE}/#person", "name": "Seongwoo Choi", "url": f"{SITE}/portfolio/"},
        "mainEntity": {
            "@type": "ItemList",
            "itemListOrder": "https://schema.org/ItemListOrderDescending",
            "numberOfItems": len(entries),
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": r["name"], "url": stars["repos"][r["repo"]]["url"]}
                for i, r in enumerate(entries, 1)
            ],
        },
    }

    page = f"""{head(title, guide["description"], url, image, json_ld)}
{NAV}
<main id="main-content" class="journal-main">
<article class="reading guide">
<header class="reading-header">
<a href="/blog/" class="back-link">← Blog</a>
<p class="kicker">{e(guide["kicker"])}</p>
<h1>{e(guide["title"])}</h1>
<p class="post-meta"><a rel="author" href="/blog/about/">Seongwoo Choi</a> · Updated <time datetime="{stars["fetched_at"]}">{updated}</time> · {len(entries)} repos · star counts from the GitHub API</p>
</header>
<div class="reading-body">
{"".join(f"<p>{e(p.replace('{count}', str(len(entries))))}</p>" for p in guide["intro"])}
<nav aria-label="In this guide"><p><strong>In this guide</strong></p><ul><li><a href="#ranking">Ranking by stars</a></li>{toc}<li><a href="#before-installing">Before you install any of these</a></li></ul></nav>
<h2 id="ranking">Ranking by stars</h2>
<p>This selection is ranked by total stars, not measured recent growth. Average stars per day is total stars divided by repository age; it is not a daily time series. The 7-day date delta appears only with snapshots dated exactly seven days apart; capture times within those days may differ.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Repos ranked by stars">
<table class="repo-table"><thead><tr><th scope="col">#</th><th scope="col">Repo</th><th scope="col" class="col-group">Group</th><th scope="col">Stars</th>{gain_th}<th scope="col">Avg/day</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
</div>
{"".join(sections)}
<h2 id="before-installing">Before you install any of these</h2>
<p>Skills and plugins are instructions your agent follows with your permissions. Install from the official repository, not a fork or a copied README. Read the skill files before enabling them, and pin a version for anything that runs in CI. Check which files are sent to a model provider, and give agents only the credentials a task needs.</p>
<div class="source-box"><h2>Sources</h2><ul>
<li>Star counts, creation dates and licenses: GitHub REST API, fetched {updated}.</li>
<li>Descriptions and check notes: each project's README on GitHub, linked from its heading above.</li>
</ul></div>
<p class="editorial-note">Projects are not presented as personally tested unless marked "From my own use." Corrections: <a href="/blog/contact/">contact</a>.</p>
</div>
</article>
</main>
{FOOTER.format(year=today.year)}"""
    (GUIDE_DIR / "index.html").write_text(page, encoding="utf-8")
    render_og_image(guide, entries, stars)
    return [(url, today.isoformat())]


def render_og_image(guide, entries, stars):
    """1200×630 PNG preview: Discover and social cards do not render SVG."""
    if not pathlib.Path(CHROME).exists():
        print("Chrome not found; skipped og.png")
        return
    e = html.escape
    top = "".join(
        f"<li><span>{e(r['name'])}</span><b>{stars['repos'][r['repo']]['stars'] / 1000:.0f}K</b></li>" for r in entries[:6]
    )
    card = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@500;700&family=Newsreader:opsz,wght@6..72,600&display=swap" rel="stylesheet">
<style>
body{{margin:0;width:1200px;height:630px;background:#f6f4ef;color:#1e1f23;font-family:'DM Sans',sans-serif;display:grid;grid-template-columns:1.15fr 1fr;gap:56px;padding:64px 72px;box-sizing:border-box}}
p{{margin:0;color:#a64b2a;font-weight:700;letter-spacing:.04em;text-transform:uppercase;font-size:22px}}
h1{{font-family:Newsreader,serif;font-weight:600;font-size:64px;line-height:1.08;letter-spacing:-.03em;margin:22px 0 0}}
small{{display:block;margin-top:34px;color:#686862;font-size:22px}}
ul{{list-style:none;margin:0;padding:0;align-self:center;border-top:2px solid #1e1f23}}
li{{display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #d8d4cb;font-size:28px}}
b{{color:#a64b2a;font-variant-numeric:tabular-nums}}
</style></head><body><div><p>{e(dt.date.fromisoformat(stars["fetched_at"][:10]).strftime("%B %Y"))}</p>
<h1>{e(guide["title"])}</h1><small>swchoi1994.github.io · {len(entries)} repos tracked</small></div><ul>{top}</ul></body></html>"""
    with tempfile.TemporaryDirectory() as tmp:
        card_path = pathlib.Path(tmp) / "card.html"
        card_path.write_text(card, encoding="utf-8")
        out = pathlib.Path(tmp) / "og.png"
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1200,630",
             "--virtual-time-budget=5000", f"--screenshot={out}", card_path.as_uri()],
            check=True, capture_output=True,
        )
        shutil.copy(out, GUIDE_DIR / "og.png")


def build():
    pages = build_repo_guide()
    urls = "".join(f"<url><loc>{loc}</loc><lastmod>{mod}</lastmod></url>" for loc, mod in pages)
    (ROOT / "sitemap-guides.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
        encoding="utf-8",
    )
    print(f"built {len(pages)} guide page(s)")


if __name__ == "__main__":
    commands = {"fetch": fetch, "build": build}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
