"""HTML templates for the blog. Plain string templates kept in one place so
the generator script stays focused on content. Edit freely."""

from __future__ import annotations

ADSENSE_CLIENT = "ca-pub-6903374993226057"

# Inserted in <head> of every blog page.
HEAD_COMMON = """\
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="index, follow">
<link rel="icon" href="/favicon.ico">
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="stylesheet" href="/blog/assets/blog.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<link rel="alternate" type="application/rss+xml" title="Seongwoo Choi - IT Blog" href="/blog/feed.xml">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=__ADSENSE__" crossorigin="anonymous"></script>
""".replace("__ADSENSE__", ADSENSE_CLIENT)

NAV = """\
<nav class="navbar">
  <div class="nav-container">
    <div class="nav-brand"><a href="/">Seongwoo Choi</a></div>
    <div class="nav-menu">
      <a href="/" class="nav-link">Home</a>
      <a href="/blog/" class="nav-link">Blog</a>
      <a href="/blog/?region=us" class="nav-link">US</a>
      <a href="/blog/?region=china" class="nav-link">China</a>
      <a href="/blog/?region=korea" class="nav-link">Korea</a>
      <a href="/blog/feed.xml" class="nav-link"><i class="fas fa-rss"></i></a>
    </div>
  </div>
</nav>
"""

AD_INLINE = """\
<div class="ad-slot">
  <ins class="adsbygoogle"
       style="display:block; text-align:center;"
       data-ad-client="__ADSENSE__"
       data-ad-slot="auto"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
""".replace("__ADSENSE__", ADSENSE_CLIENT)

NEWSLETTER_CTA = """\
<aside class="newsletter-cta">
  <h3>Get this in your inbox</h3>
  <p>A short daily digest of AI &amp; tech news from the US, China, and Korea. No spam.</p>
  <a class="cta-btn" href="https://buttondown.com/swchoi1994" rel="noopener">Subscribe</a>
  <small>Or <a href="/blog/feed.xml">grab the RSS feed</a>.</small>
</aside>
"""

FOOTER = """\
<footer class="site-footer">
  <div class="footer-inner">
    <p>&copy; <span id="year"></span> Seongwoo Choi. Built with Claude + Tavily. <a href="/blog/feed.xml">RSS</a> &middot; <a href="/sitemap.xml">Sitemap</a> &middot; <a href="/">Portfolio</a></p>
    <p class="disclaimer">Posts may include affiliate links. As an Amazon Associate and Coupang Partner, I earn from qualifying purchases. Generated daily with AI assistance and editorial review.</p>
  </div>
  <script>document.getElementById('year').textContent = new Date().getFullYear();</script>
</footer>
"""

# --- Post page ----------------------------------------------------------------

POST_PAGE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
{head_common}
<title>{title} | Seongwoo Choi</title>
<meta name="description" content="{description}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{canonical}">
<script type="application/ld+json">
{schema_json}
</script>
</head>
<body class="blog-body">
{nav}
<main class="blog-main">
  <article class="post">
    <header class="post-header">
      <div class="post-meta">
        <span class="region-tag region-{region}">{region_label}</span>
        <span class="category-tag">{category}</span>
        <time datetime="{iso_date}">{display_date}</time>
        <span class="lang-tag">{lang_label}</span>
      </div>
      <h1 class="post-title">{title}</h1>
      <p class="post-subtitle">{description}</p>
    </header>
    {ad_top}
    <div class="post-body">
{body_html}
    </div>
    {ad_mid}
    <section class="sources">
      <h3>Sources</h3>
      <ol>
{sources_html}
      </ol>
    </section>
    {newsletter_cta}
    <section class="post-nav">
      <a href="/blog/">&larr; All posts</a>
    </section>
  </article>
</main>
{footer}
</body>
</html>
"""

# --- Listing page -------------------------------------------------------------

LISTING_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
{head_common}
<title>Blog | Seongwoo Choi</title>
<meta name="description" content="Daily IT news and notes from the US, China, and Korea by Seongwoo Choi.">
<link rel="canonical" href="https://swchoi1994.github.io/blog/">
</head>
<body class="blog-body">
{nav}
<main class="blog-main">
  <header class="blog-hero">
    <h1>IT Notes from US, China &amp; Korea</h1>
    <p>Short daily posts on AI, semiconductors, startups, and the tech industry. Published every morning (KST).</p>
    <div class="region-filter">
      <button data-region="all" class="active">All</button>
      <button data-region="us">US</button>
      <button data-region="china">China</button>
      <button data-region="korea">Korea</button>
      <button data-region="en" class="lang-btn">EN</button>
      <button data-region="ko" class="lang-btn">KO</button>
    </div>
  </header>
  {ad_top}
  <section class="post-list">
{cards_html}
  </section>
  {newsletter_cta}
</main>
{footer}
<script>
  // Simple in-page filter using a query-param hook or button click.
  const params = new URLSearchParams(location.search);
  const initial = params.get('region');
  function applyFilter(value) {{
    document.querySelectorAll('.post-card').forEach(c => {{
      const r = c.dataset.region;
      const l = c.dataset.lang;
      const show = value === 'all' || r === value || l === value;
      c.style.display = show ? '' : 'none';
    }});
    document.querySelectorAll('.region-filter button').forEach(b => {{
      b.classList.toggle('active', b.dataset.region === value);
    }});
  }}
  document.querySelectorAll('.region-filter button').forEach(b => {{
    b.addEventListener('click', () => applyFilter(b.dataset.region));
  }});
  if (initial) applyFilter(initial);
</script>
</body>
</html>
"""

CARD = """\
<a class="post-card" data-region="{region}" data-lang="{lang}" href="{url}">
  <div class="card-meta">
    <span class="region-tag region-{region}">{region_label}</span>
    <span class="lang-tag">{lang_label}</span>
    <time datetime="{iso_date}">{display_date}</time>
  </div>
  <h2>{title}</h2>
  <p>{description}</p>
  <span class="read-more">Read &rarr;</span>
</a>
"""
