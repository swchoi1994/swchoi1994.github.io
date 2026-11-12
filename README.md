# Seongwoo Choi Journal

A static publication built from the existing, externally synchronized English articles. The public homepage is a journal; the former CV homepage lives at `/portfolio/`.

## Build and preview

```sh
python3 tools/publish.py
python3 -m unittest discover -s tools -p 'test_*.py'
python3 -m http.server 8791 --bind 127.0.0.1 --directory _site
```

Python's standard library is sufficient for the build and CI checks. For optional browser regression checks, serve `_site` on port 8791 and run `node tools/browser-smoke.cjs` with an installed Playwright; this checks every page type at five widths, dark mode, the cards/list toggle, search, legacy links, the phone menu and the ad blocker notice. `_site/` is generated and ignored. The root `index.html` is a checked-in homepage preview; deployment always regenerates it from current articles.

The upstream sync job still owns `blog/posts/`, `blog/index.html`, `blog/feed.xml`, and its media. Do not manually redesign those generated inputs. `tools/publish.py` reads them and renders every journal page through one shared shell (`page()`): sidebar, phone top bar, dark mode, search, metadata and structured data. New sync commits automatically trigger `.github/workflows/pages.yml`. Failed builds/tests leave the previously deployed site intact.

The existing guide generator remains `tools/guides.py`; the publication build wraps its output in the same shell. The journal's styles and behaviour live in `assets/css/journal.css` and `assets/js/journal.js`; `assets/css/style.css` now serves the portfolio only. The visual rules are in `DESIGN.md`.

## Which articles are published

Posts written for the Korean Naver blog only (tax, welfare, housing and similar Korea-specific guidance) are left off the English site. The build recognises them by their sources: any article citing a domain listed under `naver_only.source_domains` in `content/site.json` (Korean government and public-institution domains) is skipped, removed from the feed, sitemap, search index and output, and listed in the build log. To override a single article, add its ID to `naver_only.posts` (always skip) or `naver_only.keep` (always publish).

## Articles written in this repository

Most articles arrive through the sync. An article can also be written here: add `content/posts/<slug>.html`, where the file name becomes the URL (`/blog/posts/<slug>/`). The file starts with an HTML comment holding JSON metadata, followed by the body as plain HTML (`<p>`, `<h2 id="...">`, lists, `<pre><code>`, tables):

```html
<!--
{
  "title": "At most 60 characters",
  "description": "At most 160 characters",
  "date": "2026-11-12T09:00:00+00:00",
  "topic": "ai-automation",
  "note": "How the article was checked, and what was not tested.",
  "sources": [{"title": "Name of the source", "url": "https://..."}]
}
-->
<p>First paragraph.</p>
<h2 id="first-section">1. First section</h2>
```

The build adds the byline, the contents list from the `<h2 id>` headings, the source list, the feed entry and the structured data. These articles have no Korean original, and end with a note saying they were written for this site with AI assistance. The tests hold them to a stricter bar than synced posts: title and description lengths, at least two `https` sources, a `note`, and at least three sections. Write the `note` honestly; say plainly when commands were not run.

### Series and projects

Two optional metadata fields turn single articles into a course:

```json
"series": "vllm-server",
"part": 2,
"project": {"needs": "What the reader must have before starting.", "result": "What is running at the end."}
```

- `series` must be a key in `content/series.json`, which holds each series' `title` and `description`. Parts must run 1, 2, 3 with no gaps or repeats, or the build stops. Each part then shows where it sits in the series, links to the previous and next part, and appears on `/series/<slug>/` in reading order. The home page and `/series/` list every series.
- `project` marks a follow-along article. Its two lines appear under the summary and on `/projects/`, which lists projects easiest first.

The Series and Projects links appear in the sidebar only while at least one article uses them.

## Owner settings

Everything below is off until its values are filled in. No IDs are invented by the build.

| File | Purpose |
| --- | --- |
| `content/site.json` → `ads` | AdSense ad unit IDs for the fixed slots: `rail` (right margin and article rail), `article_end`, `between` (home sections), `footer`. Empty slots render nothing; Auto ads are unaffected. |
| `content/site.json` → `comments` | giscus settings (`repo`, `repo_id`, `category`, `category_id`) from giscus.app after enabling Discussions and installing the giscus app. Comments load only when a reader opens them. Update the privacy page before enabling. |
| `content/site.json` → `verification` | Search engine ownership codes: `google` (the `content` value of Search Console's HTML tag) and `bing`. A filled value adds the matching `<meta>` tag to the home page only. The Google property is currently verified through the Analytics tag; adding the HTML tag as well gives a second method. |
| `content/series.json` | The series that articles can join: `{slug: {title, description}}`. See "Series and projects". |
| `content/site.json` → `article_cover` | `true` shows the cover illustration inside articles. Default `false`: covers are used for social previews only. |
| `content/post-meta.json` | Optional per-article `mood` and `music`, keyed by article ID, shown under the byline. Enter these by hand; leave an article out to show nothing. |
| `content/x-posts.json` | The posts shown under "On X" on the home page (date, text, link). X does not offer a public feed, so this list is maintained by hand. |

When the AdSense script fails to load, the reader sees one of two things, chosen by `adblock_wall` in `content/site.json`:

- `true` (current): a wall. The page is blurred and paused until the reader allows ads and reloads. It offers a link to the contact page for false alarms.
- `false`: a dismissible notice that never blocks reading and stays hidden for a week once dismissed.

Either way, the About, Contact, Editorial and Privacy pages carry no ad script and so never show it. Search crawlers and headless test browsers are recognised by their user agent and are not walled, because they never load ads. The wall cannot tell an ad blocker from a privacy setting, VPN or network filter that blocks the same script; those readers are walled too.

## Editorial controls

- `AI_PICKS` in `tools/publish.py` selects the 15 featured articles on the home page in five groups by stable upstream ID; `PICKS` and `STARTERS` select guide and topic starting points. They are editor selections, never claimed traffic rankings.
- `TITLES` contains carefully shortened display titles. Headings, social metadata, RSS, search and structured data use the same title. The browser/search `<title>` is shortened further to the clause before the first colon when the full title is over 60 characters; titles with no such clause stay long until they are given a `TITLES` entry.
- Topic assignment uses the article title. Check the generated topic page when publishing an unfamiliar subject; extend `topic_for` and its focused test if needed.
- Article URLs, original publication dates, source citations and the Korean-original attribution remain intact. Sources are not a substitute for fact-checking. No new firsthand testing claims are generated.

## Search and AI search

- Every page has one `<h1>`, a self-canonical URL, a description of at most 160 characters, Open Graph and Twitter tags with a raster image and its dimensions, and breadcrumbs.
- Articles carry `BlogPosting` data with `datePublished`, `dateModified`, the author, the topic, and `isBasedOn` pointing at the Korean original. The home page declares the site search.
- After each deploy, `tools/indexnow.py` submits the pages changed in the last day to IndexNow, which Bing, Naver and Yandex read. It uses the key file already served at the site root and never fails the deploy.
- The sitemap lists every page, with `lastmod` on articles and listing pages. `llms.txt` gives AI assistants a short map of the topics and featured guides. `robots.txt` blocks no crawler.
- In article bodies the build turns runs of "①, ②, ③" paragraphs into ordered lists and gives the source list the descriptive link text already used in the article. Nothing else in the text is rewritten.
- AI search uses the same textual pages as human readers; there is no hidden AI-only content or citation guarantee.

## Article images

Each current article has an original AI-generated editorial cover. It is used for social previews and article metadata; lists and cards are text-only, and the cover appears inside the article only when `article_cover` is enabled in `content/site.json`. Captions identify illustrations as distinct from product screenshots.

`content/article-images.json` records image paths, dimensions, alt text, credit and generation prompts. Assets live in `assets/img/articles/` as 640px and 1200px WebP variants. Newly synchronized articles without a cover use the site card `assets/img/og-default.png` for social previews until a cover is imported, because social scrapers do not render their SVG illustration.

To import a generated image for an existing article (Pillow is needed locally for this step only):

```sh
python3 tools/import_article_image.py naver-ARTICLE_ID /path/to/generated.png 'Generation prompt' 'Descriptive alt text'
python3 tools/publish.py
```

Use original illustrations or images with documented reuse permission. Search results alone do not grant reuse rights. Actual screenshots and test results should come from verified demonstrations, not image generation. The build and CI remain standard-library-only.

Selected articles also have a `reference` in their image manifest entry: an unchanged Microsoft Support screenshot with dimensions, descriptive caption, source and original image URLs, permission URL, and review date. These appear before the source list with the required permission notice; they are attributed reference examples, not evidence of the author's testing. Review the actual image and current reuse terms before adding one. Reimporting a cover preserves its reference screenshot.

## Monetization

The existing AdSense publisher ID and `ads.txt` are preserved. Account approval, Auto ads settings and Google's consent configuration remain controlled by the owner in AdSense; the code does not invent ad-slot IDs or certify the account is approved. Fixed slots are described under Owner settings and in `DESIGN.md`: they sit at the page edges and after the article, never inside the text or navigation. Use the existing contact page for sponsorship and project inquiries.

About, contact, editorial and privacy pages stay ad-free: their shared shell omits the AdSense loader, fixed slots and ad-blocker notice, including when ad units are configured. The portfolio and setup tools also retain their ad-free pages. This preserves the upstream sync validator's advertising boundary.

The Amazon affiliate build step is **inactive until the owner supplies marketplace and tracking ID** in `content/affiliates.json`. No API keys are needed for ordinary product links. The ID must belong to the approved site/account and marketplace.

Example format (documentation only; these are not real product recommendations):

```json
{
  "marketplace": "amazon.com",
  "tracking_id": "YOUR-REAL-TAG-20",
  "placements": {
    "naver-ARTICLE_ID": [
      {
        "asin": "B012345678",
        "title": "Accurate product name",
        "reason": "Why this specific product is relevant; include compatibility limits."
      }
    ]
  }
}
```

On every deployment the build:

1. Validates the owner configuration, article IDs and product IDs.
2. Adds selected product links before the source list.
3. Applies the tracking ID to direct product links on the selected Amazon marketplace only.
4. Marks those links `rel="sponsored nofollow noopener"` and puts Amazon's disclosure above affected articles.

Other marketplaces, short links, redirects and lookalike domains are left unchanged. Product titles/reasons are escaped. There is no scraping, price/rating fabrication, copied Amazon imagery, or automatic recommendation of unrelated products. Verify the product and its fit before adding a placement. For short links, use the direct Amazon product URL first.

Disclosure requirement: https://affiliate-program.amazon.com/help/node/topic/GHQNZAU6669EZS98

## Publishing and rollback

GitHub Pages must use **GitHub Actions** as its publishing source. The workflow tests the generated site before uploading only `_site/`, then deploys it. It does not commit build output, avoiding conflicts with the upstream content sync. Local preview artifacts and tooling are not deployed.

For a regression, revert the responsible commit and push; the same workflow rebuilds and deploys. For the pre-publication layout, restore the previous root `index.html` and set Pages back to its original branch source (`main`, `/`).

## Measuring growth

Use Search Console for organic clicks and query/page performance, and AdSense for page RPM and revenue. Review them monthly alongside the pages changed. The owner-configured GA4 property is preserved by the publication build. Affiliate earnings are reported by Amazon. These foundations do not promise traffic, approval, citations or revenue.

## Search Console ownership

For this GitHub-owned `github.io` subdomain, use a URL-prefix property for `https://swchoi1994.github.io/`. The repository cannot set GitHub's DNS TXT records. Verify it with the Google Analytics tag that is already on every page, or obtain the HTML verification tag from that property and put its `content` value in `content/site.json` under `verification.google`; do not substitute a token copied from the Domain-property DNS screen. After deployment, verify in Search Console and submit `https://swchoi1994.github.io/sitemap.xml`.
