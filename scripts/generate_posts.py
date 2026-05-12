"""Daily blog post generator.

Pipeline:
  1. For each item in voice.json -> post_plan.daily:
       a. Pull fresh news via Tavily search for the chosen region.
       b. Ask Claude (or OpenAI fallback) to write a post in the configured
          voice and language, citing the sources.
       c. Render an HTML post page, append to the index of all posts.
  2. Rebuild the blog listing page (/blog/index.html), the RSS feed, and the
     sitemap.

Run locally:
    TAVILY_API_KEY=... ANTHROPIC_API_KEY=... python scripts/generate_posts.py

Run with --dry-run to test without writing any files.
Run with --backfill N to generate N days of historical posts (stubbed dates).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

import templates as T

ROOT = Path(__file__).resolve().parents[1]
BLOG_DIR = ROOT / "blog"
POSTS_DIR = BLOG_DIR / "posts"
DATA_DIR = BLOG_DIR / "data"
INDEX_JSON = DATA_DIR / "index.json"
VOICE_PATH = Path(__file__).resolve().parent / "voice.json"

SITE_URL = "https://swchoi1994.github.io"


# ---------- Helpers -----------------------------------------------------------

def log(msg: str) -> None:
    print(f"[gen] {msg}", flush=True)


def slugify(s: str, max_len: int = 60) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rsplit("-", 1)[0]
    if not s:
        s = "post"
    return s


def load_voice() -> dict:
    return json.loads(VOICE_PATH.read_text(encoding="utf-8"))


def load_index() -> list[dict]:
    if INDEX_JSON.exists():
        return json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    return []


def save_index(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_JSON.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------- News fetch (Tavily) ----------------------------------------------

def tavily_search(query: str, *, max_results: int = 6) -> list[dict]:
    """Call Tavily Search API. Returns a list of {title, url, content} dicts."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        log("TAVILY_API_KEY missing - returning empty result set")
        return []
    import urllib.request

    payload = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "topic": "news",
            "days": 2,
            "include_answer": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"Tavily error for query {query!r}: {e}")
        return []
    return data.get("results", []) or []


def gather_news(voice: dict, region: str, *, max_items: int = 8) -> list[dict]:
    queries = voice["regions"][region]["search_queries"]
    seen_urls: set[str] = set()
    items: list[dict] = []
    for q in queries:
        for r in tavily_search(q, max_results=4):
            url = r.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(
                {
                    "title": r.get("title", "").strip(),
                    "url": url,
                    "content": (r.get("content") or "").strip(),
                    "published": r.get("published_date"),
                }
            )
            if len(items) >= max_items:
                return items
    return items


# ---------- LLM call ----------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """You are {author_name}, an AI engineer based in Seoul who writes a personal IT blog.
Your job is to take a small set of source articles and produce ONE original blog post
in the language and tone described below. Do not invent facts that are not present in the sources.
Always cite sources with numbered footnote-style references like [1], [2] that match the order I provide.

Voice ({lang}): {tone}

Structure (use these sections, in order, but use natural prose - do NOT print the literal section names):
{sections}

Length target: {min_words}-{max_words} words.

Output format: STRICT JSON, no markdown fences, with these exact keys:
{{
  "title": "string - headline that would work for SEO and human readers, < 80 chars",
  "description": "string - 1-2 sentence meta description, < 200 chars",
  "category": "string - one of: {categories}",
  "body_markdown": "string - the post body in Markdown. Use ## for sub-headings if helpful. Use [n] inline citations referring to the numbered sources you receive."
}}
Do not include any text outside the JSON object.
"""


def llm_complete(system: str, user: str) -> str:
    """Return raw text completion. Tries Anthropic Claude, then OpenAI."""
    anth_key = os.environ.get("ANTHROPIC_API_KEY")
    oai_key = os.environ.get("OPENAI_API_KEY")
    if anth_key:
        return _claude(system, user, anth_key)
    if oai_key:
        return _openai(system, user, oai_key)
    raise RuntimeError("Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set")


def _claude(system: str, user: str, key: str) -> str:
    import urllib.request

    body = json.dumps(
        {
            "model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            "max_tokens": 4000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    parts = data.get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def _openai(system: str, user: str, key: str) -> str:
    import urllib.request

    body = json.dumps(
        {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def write_post(voice: dict, lang: str, region: str, news: list[dict]) -> dict | None:
    if not news:
        log(f"no news items for {lang}/{region}; skipping")
        return None
    tone = voice["tone"][lang]
    categories = ", ".join(voice["categories"])
    sections = "\n".join(f"- {s}" for s in voice["structure"]["sections"])
    min_words = voice["structure"][f"min_words_{lang}"]
    max_words = voice["structure"][f"max_words_{lang}"]
    system = SYSTEM_PROMPT_TEMPLATE.format(
        author_name=voice["author"]["name"],
        lang="Korean" if lang == "ko" else "English",
        tone=tone,
        sections=sections,
        min_words=min_words,
        max_words=max_words,
        categories=categories,
    )
    # Limit per-item snippet to keep prompt small.
    numbered = []
    for i, n in enumerate(news, 1):
        snippet = (n["content"] or "")[:1200]
        numbered.append(f"[{i}] {n['title']}\nURL: {n['url']}\nSnippet: {snippet}")
    user = (
        f"Region: {voice['regions'][region]['label_en']}.\n"
        f"Date: {dt.date.today().isoformat()}.\n\n"
        "SOURCES (cite by number):\n\n" + "\n\n".join(numbered)
    )
    raw = llm_complete(system, user).strip()
    # Strip ```json fences if the model added them.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"model returned non-JSON, attempting recovery: {e}")
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            log("could not recover JSON; skipping post")
            return None
        data = json.loads(m.group(0))
    data["sources"] = [{"title": n["title"], "url": n["url"]} for n in news]
    data["lang"] = lang
    data["region"] = region
    return data


# ---------- Markdown -> HTML (tiny, no deps) ---------------------------------

def md_to_html(md: str) -> str:
    """Minimal markdown renderer. Handles ##/###, paragraphs, **bold**, *italic*,
    inline code, fenced code blocks, [text](url), and simple lists.
    Good enough for our generated posts; intentionally not feature complete."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    in_code = False
    code_buf: list[str] = []
    in_list = False
    para: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            text = " ".join(para).strip()
            if text:
                out.append(f"<p>{_inline(text)}</p>")
            para = []

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def _inline(s: str) -> str:
        s = html.escape(s)
        # links [text](url) - we must run BEFORE bold/italic so we don't break URLs
        s = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda m: f'<a href="{m.group(2)}" rel="noopener">{m.group(1)}</a>',
            s,
        )
        # inline code
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        # bold then italic
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        # numbered citations [1] -> link to sources list
        s = re.sub(
            r"\[(\d+)\]",
            r'<a class="cite" href="#src-\1">[\1]</a>',
            s,
        )
        return s

    for ln in lines:
        if ln.startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                flush_para()
                close_list()
                in_code = True
            continue
        if in_code:
            code_buf.append(ln)
            continue
        if not ln.strip():
            flush_para()
            close_list()
            continue
        m = re.match(r"^(#{2,4})\s+(.*)$", ln)
        if m:
            flush_para()
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2).strip())}</h{level}>")
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", ln)
            out.append(f"<li>{_inline(item)}</li>")
            continue
        para.append(ln.strip())

    flush_para()
    close_list()
    if in_code and code_buf:
        out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
    return "\n".join(out)


# ---------- Rendering --------------------------------------------------------

def render_post(post: dict, voice: dict) -> tuple[Path, dict]:
    today = dt.date.today()
    iso = today.isoformat()
    slug = slugify(post["title"])
    rel = f"posts/{today.year}/{today.month:02d}/{today.day:02d}/{post['region']}-{post['lang']}-{slug}/"
    out_dir = BLOG_DIR / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    canonical = f"{SITE_URL}/blog/{rel}"

    region = post["region"]
    lang = post["lang"]
    region_label = voice["regions"][region][f"label_{lang}"] if lang == "ko" else voice["regions"][region]["label_en"]
    lang_label = "한국어" if lang == "ko" else "English"
    body_md = post.get("body_markdown", "")
    body_html = md_to_html(body_md)

    sources_html_parts: list[str] = []
    for i, s in enumerate(post.get("sources", []), 1):
        sources_html_parts.append(
            f'<li id="src-{i}"><a href="{html.escape(s["url"])}" rel="noopener" target="_blank">{html.escape(s["title"] or s["url"])}</a></li>'
        )

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post.get("description", ""),
        "author": {"@type": "Person", "name": voice["author"]["name"], "url": voice["author"]["site"]},
        "datePublished": iso,
        "dateModified": iso,
        "inLanguage": "ko-KR" if lang == "ko" else "en-US",
        "mainEntityOfPage": canonical,
        "publisher": {"@type": "Person", "name": voice["author"]["name"]},
    }

    html_out = T.POST_PAGE.format(
        lang="ko" if lang == "ko" else "en",
        head_common=T.HEAD_COMMON,
        nav=T.NAV,
        footer=T.FOOTER,
        ad_top=T.AD_INLINE,
        ad_mid=T.AD_INLINE,
        newsletter_cta=T.NEWSLETTER_CTA,
        title=html.escape(post["title"]),
        description=html.escape(post.get("description", "")),
        category=html.escape(post.get("category", "Tech")),
        region=region,
        region_label=html.escape(region_label),
        lang_label=lang_label,
        iso_date=iso,
        display_date=today.strftime("%B %d, %Y") if lang != "ko" else today.strftime("%Y년 %m월 %d일"),
        canonical=canonical,
        body_html=body_html,
        sources_html="\n".join(sources_html_parts),
        schema_json=json.dumps(schema, ensure_ascii=False, indent=2),
    )
    out_file.write_text(html_out, encoding="utf-8")

    record = {
        "title": post["title"],
        "description": post.get("description", ""),
        "category": post.get("category", "Tech"),
        "region": region,
        "lang": lang,
        "date": iso,
        "path": f"/blog/{rel}",
        "sources": post.get("sources", []),
    }
    return out_file, record


def render_listing(index: list[dict]) -> None:
    cards: list[str] = []
    for r in sorted(index, key=lambda x: x["date"], reverse=True):
        cards.append(
            T.CARD.format(
                region=r["region"],
                lang=r["lang"],
                url=r["path"],
                region_label=html.escape(r["region"].upper()),
                lang_label="한국어" if r["lang"] == "ko" else "English",
                iso_date=r["date"],
                display_date=r["date"],
                title=html.escape(r["title"]),
                description=html.escape(r["description"]),
            )
        )
    page = T.LISTING_PAGE.format(
        head_common=T.HEAD_COMMON,
        nav=T.NAV,
        footer=T.FOOTER,
        ad_top=T.AD_INLINE,
        newsletter_cta=T.NEWSLETTER_CTA,
        cards_html="\n".join(cards) or "<p>No posts yet. Check back tomorrow.</p>",
    )
    (BLOG_DIR / "index.html").write_text(page, encoding="utf-8")


def render_rss(index: list[dict]) -> None:
    items_xml = []
    for r in sorted(index, key=lambda x: x["date"], reverse=True)[:50]:
        items_xml.append(
            f"""    <item>
      <title>{html.escape(r['title'])}</title>
      <link>{SITE_URL}{r['path']}</link>
      <guid isPermaLink="true">{SITE_URL}{r['path']}</guid>
      <pubDate>{dt.datetime.fromisoformat(r['date']).strftime('%a, %d %b %Y 06:00:00 +0900')}</pubDate>
      <description>{html.escape(r['description'])}</description>
      <category>{html.escape(r['region'])}</category>
    </item>"""
        )
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Seongwoo Choi - IT Blog</title>
    <link>{SITE_URL}/blog/</link>
    <atom:link href="{SITE_URL}/blog/feed.xml" rel="self" type="application/rss+xml" />
    <description>Daily IT news and notes from US, China, and Korea.</description>
    <language>en-us</language>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
    (BLOG_DIR / "feed.xml").write_text(rss, encoding="utf-8")


def render_sitemap(index: list[dict]) -> None:
    urls = [SITE_URL + "/", SITE_URL + "/blog/"]
    urls.extend(SITE_URL + r["path"] for r in index)
    body = "\n".join(
        f"  <url><loc>{u}</loc></url>" for u in urls
    )
    sm = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
"""
    (ROOT / "sitemap.xml").write_text(sm, encoding="utf-8")


# ---------- Main -------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Generate but do not write files")
    p.add_argument("--limit", type=int, default=None, help="Generate at most N posts")
    p.add_argument("--seed-fixture", action="store_true",
                   help="Generate seed posts from local fixtures (no Tavily/LLM). Used for first deploy.")
    args = p.parse_args(argv)

    voice = load_voice()
    index = load_index()
    existing_paths = {r["path"] for r in index}

    plan = voice["post_plan"]["daily"]
    if args.limit:
        plan = plan[: args.limit]

    today_iso = dt.date.today().isoformat()
    new_records: list[dict] = []

    for slot in plan:
        lang = slot["lang"]
        region = slot["region"]
        log(f"working on {lang}/{region}")
        try:
            if args.seed_fixture:
                from seed_fixtures import build_seed_post
                post = build_seed_post(lang, region, voice)
            else:
                news = gather_news(voice, region)
                post = write_post(voice, lang, region, news)
        except Exception as e:  # noqa: BLE001
            log(f"failed to generate {lang}/{region}: {e}")
            continue
        if not post:
            continue
        if args.dry_run:
            log(f"[dry-run] would write: {post['title']!r}")
            continue
        _, record = render_post(post, voice)
        # Skip if this slug already exists today (e.g. rerun on same day)
        if record["path"] in existing_paths:
            log(f"already exists, skipping: {record['path']}")
            continue
        new_records.append(record)
        existing_paths.add(record["path"])
        log(f"wrote {record['path']}")
        time.sleep(1)

    if args.dry_run:
        log("dry-run complete")
        return 0

    if new_records or not (BLOG_DIR / "index.html").exists():
        index.extend(new_records)
        save_index(index)
        render_listing(index)
        render_rss(index)
        render_sitemap(index)
        log(f"rebuilt listing, RSS, sitemap. {len(new_records)} new posts.")
    else:
        log("no new posts; nothing to rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main())
