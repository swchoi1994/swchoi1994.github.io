# Daily IT Blog Generator

Auto-publishes 3 IT posts per day (US, China, Korea — mixed EN/KO) to `/blog/` on this GitHub Pages site. Runs on a GitHub Actions cron at **21:00 UTC = 06:00 KST**.

## How it works

```
voice.json  ──┐
              │
              ▼
   Tavily search (per region)  ──►  Claude / GPT writer  ──►  HTML render  ──►  git commit & push
              ▲                                                       │
              │                                                       ▼
   regions.search_queries                                  /blog/posts/YYYY/MM/DD/...
                                                          /blog/index.html (listing)
                                                          /blog/feed.xml   (RSS)
                                                          /sitemap.xml
```

- `scripts/voice.json` — author bio, tone (EN + KO), structure, regions and search queries, daily post plan. **Edit this to change the blog's voice.**
- `scripts/generate_posts.py` — main pipeline.
- `scripts/templates.py` — HTML templates for posts + listing.
- `scripts/seed_fixtures.py` — placeholder posts for first deploy (no API needed).
- `.github/workflows/daily-blog.yml` — cron + manual dispatch.

## Required GitHub secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Required | Notes |
|---|---|---|
| `TAVILY_API_KEY` | yes | https://tavily.com — free tier covers daily runs |
| `ANTHROPIC_API_KEY` | optional | Only needed if you want to bypass GitHub Models |
| `OPENAI_API_KEY` | optional | Same — fallback only |

### LLM access: GitHub Models (free, default)

The generator uses **GitHub Models** by default — a free, official endpoint that gives you `gpt-4o-mini`, `gpt-4o`, Llama 3.3, Mistral, and others. Auth uses the `GITHUB_TOKEN` that's automatically present in every GitHub Action, so **no extra secret is required**.

Rate limits (free tier, roughly):
- `gpt-4o-mini`: ~15 req/min, 150 req/day
- `gpt-4o`: ~10 req/min, 50 req/day

At 3–6 posts/day, you'll never hit them.

Override the model by setting a repo variable `GITHUB_MODELS_MODEL` (e.g. `openai/gpt-4o`, `meta/llama-3.3-70b-instruct`, `mistral-ai/mistral-small-2503`).

Provider preference order in code: `GITHUB_TOKEN` → `ANTHROPIC_API_KEY` → `OPENAI_API_KEY`.

Optional env: `CLAUDE_MODEL` (default `claude-sonnet-4-6`), `OPENAI_MODEL` (default `gpt-4o-mini`), `GITHUB_MODELS_MODEL` (default `openai/gpt-4o-mini`).

## Local run

```bash
# Real run (uses APIs - costs ~$0.10/day on Claude Sonnet)
export TAVILY_API_KEY=...
export ANTHROPIC_API_KEY=...
python3 scripts/generate_posts.py

# Dry run (no files written)
python3 scripts/generate_posts.py --dry-run

# Seed initial content (no API keys needed)
python3 scripts/generate_posts.py --seed-fixture
```

## Adjusting the schedule

Edit `.github/workflows/daily-blog.yml` → `cron`. Examples:

- `0 21 * * *` — every day at 6 AM KST (current)
- `0 21 * * 1-5` — weekdays only
- `0 21,9 * * *` — twice a day (6 AM and 6 PM KST)

## Adjusting volume / topics

In `voice.json`:

- `post_plan.daily` — add or remove entries to publish more/fewer posts per day. Example to publish 6 posts/day:
  ```json
  "daily": [
    {"lang": "en", "region": "us"},
    {"lang": "ko", "region": "us"},
    {"lang": "en", "region": "china"},
    {"lang": "ko", "region": "china"},
    {"lang": "en", "region": "korea"},
    {"lang": "ko", "region": "korea"}
  ]
  ```
- `regions.<region>.search_queries` — add more Tavily queries to broaden the news pool.
- `tone.en` / `tone.ko` — refine the voice. Paste sample paragraphs from your Naver blog directly into this field for a closer tonal match.

## Monetization

- **Google AdSense** is already wired (`pub-6903374993226057`). The post template inserts two responsive auto-ad slots: one above the body, one mid-article. AdSense will auto-fill once your domain is approved.
- **Affiliate disclosure** is in the footer; replace with your actual affiliate links once approved (Amazon Associates, Coupang Partners).
- **Newsletter CTA** points to `buttondown.com/swchoi1994` — sign up there (free up to 100 subs) or replace with your provider in `templates.py`.

### Realistic revenue expectations

A brand-new auto-generated blog will not earn $500–1000/day on day one. AdSense typically pays $1–5 RPM (revenue per 1000 pageviews). To hit $500/day from ads alone you need ~100K–500K daily pageviews, which usually takes 6–18 months of consistent SEO-friendly publishing plus active distribution (Twitter/X, LinkedIn, Hacker News, Korean dev communities). Diversifying with affiliate links, sponsored posts ($100–500/post once you have audience), and a paid newsletter is the realistic path to $500+/day.

## SEO / Distribution checklist

- [ ] Verify the domain in Google Search Console and submit `/sitemap.xml`
- [ ] Verify in Naver Search Advisor (for Korean traffic)
- [ ] Verify in Bing Webmaster Tools
- [ ] Set up Google Analytics 4 (replace placeholder in templates if you want analytics)
- [ ] Share new posts to X/Twitter, LinkedIn, Korean dev communities (OKKY, 클리앙)
- [ ] Submit RSS feed to Feedly, Inoreader

## Initial deploy steps

1. **Add the three GitHub secrets above.**
2. Merge `claude/personal-it-blog-kHYqq` into `main` (or have the bot push directly to main going forward).
3. Trigger the workflow manually once via **Actions → Daily blog post → Run workflow** to confirm wiring.
4. The next scheduled run (6 AM KST) will publish the first real posts.

The first three sample posts shipped in this branch are placeholders generated from `seed_fixtures.py` so the listing page isn't empty on the first deploy. They'll be supplemented (not replaced) by real Tavily-sourced posts from the next cron run.
