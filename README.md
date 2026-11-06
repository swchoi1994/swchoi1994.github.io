# Seongwoo Choi Journal

A static publication built from the existing, externally synchronized English articles. The public homepage is a journal; the former CV homepage lives at `/portfolio/`.

## Build and preview

```sh
python3 tools/publish.py
python3 -m unittest discover -s tools -p 'test_*.py'
python3 -m http.server 8000 --directory _site
```

Python's standard library is sufficient for the build and CI checks. For optional browser regression checks, serve `_site` on port 8791 and run `node tools/browser-smoke.cjs` with the already-installed `@playwright/test` and Chrome; this checks mobile/desktop layout, search failure states, legacy links, and navigation without JavaScript. `_site/` is generated and ignored. The root `index.html` is a checked-in homepage preview; deployment always regenerates it from current articles.

The upstream sync job still owns `blog/posts/`, `blog/index.html`, `blog/feed.xml`, and its media. Do not manually redesign those generated inputs. `tools/publish.py` reads them, applies publication navigation, local English links, article summaries, related reading, metadata, affiliate rules, topic pages, search, and pagination into `_site/`. New sync commits automatically trigger `.github/workflows/pages.yml`. Failed builds/tests leave the previously deployed site intact.

The existing guide generator remains `tools/guides.py`; the publication build incorporates its output. Styles specific to the publication live in `assets/css/publication.css`.

## Editorial controls

- `AI_PICKS` in `tools/publish.py` selects the 15 homepage articles in five groups by stable upstream ID; `PICKS` and `STARTERS` select guide and topic starting points. They are editor selections, never claimed traffic rankings.
- `TITLES` contains carefully shortened display titles. Headings, social metadata, RSS, search and structured data use the same title.
- Topic assignment uses the article title. Check the generated topic page when publishing an unfamiliar subject; extend `topic_for` and its focused test if needed.
- Article URLs, original publication dates, source citations and the Korean-original attribution remain intact. Sources are not a substitute for fact-checking. No new firsthand testing claims are generated.
- AI search uses the same textual pages as human readers. The complete sitemap, author profile, breadcrumbs, answer summaries and source links provide context; there is no hidden AI-only content or citation guarantee.

## Article images

Each current article has an original AI-generated editorial cover, displayed on the article, archive, topic pages, homepage and search results. Captions identify illustrations as distinct from product screenshots. The build also uses the cover for social previews and article metadata.

`content/article-images.json` records image paths, dimensions, alt text, credit and generation prompts. Assets live in `assets/img/articles/` as 640px and 1200px WebP variants. Below-the-fold images load lazily; dimensions reserve layout space. Newly synchronized articles without a cover retain their existing SVG illustration until a cover is imported.

To import a generated image for an existing article (Pillow is needed locally for this step only):

```sh
python3 tools/import_article_image.py naver-ARTICLE_ID /path/to/generated.png 'Generation prompt' 'Descriptive alt text'
python3 tools/publish.py
```

Use original illustrations or images with documented reuse permission. Search results alone do not grant reuse rights. Actual screenshots and test results should come from verified demonstrations, not image generation. The build and CI remain standard-library-only.

## Monetization

The existing AdSense publisher ID and `ads.txt` are preserved. Account approval, Auto ads settings and Google's consent configuration remain controlled by the owner in AdSense; the code does not invent ad-slot IDs or certify the account is approved. Keep advertising out of navigation and away from controls. Use the existing contact page for sponsorship and project inquiries.

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

For this GitHub-owned `github.io` subdomain, use a URL-prefix property for `https://swchoi1994.github.io/`. The repository cannot set GitHub's DNS TXT records. Obtain the HTML verification tag from that property and add it to the homepage `<head>` generated by `tools/publish.py`; do not substitute a token copied from the Domain-property DNS screen. After deployment, verify in Search Console and submit `https://swchoi1994.github.io/sitemap.xml`.
