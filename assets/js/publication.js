(() => {
  'use strict';
  // Keep bookmarks to the former CV homepage working after its move.
  const redirectLegacy = () => {
    if (location.pathname === '/' && ['#work', '#experience', '#research', '#education', '#contact'].includes(location.hash)) {
      location.replace(`/portfolio/${location.hash}`);
      return true;
    }
    if (location.pathname === '/blog/' && location.hash === '#media') {
      location.replace('/videos/');
      return true;
    }
    return false;
  };
  if (redirectLegacy()) return;
  window.addEventListener('hashchange', redirectLegacy);
  for (const link of document.querySelectorAll('.nav-link')) {
    if (new URL(link.href).pathname === location.pathname) link.setAttribute('aria-current', 'page');
  }
  const form = document.querySelector('.archive-search');
  if (!form) return;
  const input = document.getElementById('archive-search');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const archive = document.getElementById('archive-content');
  let index;
  let request = 0;
  async function search() {
    const current = ++request;
    const query = input.value.trim();
    const terms = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const url = new URL(location.href);
    if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
    history.replaceState(null, '', url);
    results.replaceChildren();
    results.hidden = true;
    archive.hidden = false;
    if (!terms.length) { status.textContent = ''; return; }
    status.textContent = 'Searching…';
    try {
      if (!index) {
        const response = await fetch('/blog/search-index.json');
        if (!response.ok) throw new Error('Search unavailable');
        index = await response.json();
      }
      if (current !== request) return;
      const matches = index.filter(post => terms.every(term => `${post.title} ${post.description}`.toLocaleLowerCase().includes(term)));
      for (const post of matches) {
        const article = document.createElement('article');
        article.className = 'story';
        const image = document.createElement('img');
        image.src = post.image.small || post.image.src;
        image.alt = '';
        image.width = post.image.width;
        image.height = post.image.height;
        image.loading = 'lazy';
        image.decoding = 'async';
        const visual = document.createElement('div');
        visual.className = 'story-image';
        visual.append(image);
        const title = document.createElement('h3');
        const link = document.createElement('a');
        link.href = post.url;
        link.textContent = post.title;
        title.append(link);
        const description = document.createElement('p');
        description.className = 'story-description';
        description.textContent = post.description;
        article.append(visual, title, description);
        results.append(article);
      }
      status.textContent = matches.length ? `${matches.length} article${matches.length === 1 ? '' : 's'} found.` : 'No matches. Try fewer words or browse a topic above.';
      results.hidden = false;
      archive.hidden = true;
    } catch {
      if (current === request) status.textContent = 'Search is temporarily unavailable. You can still browse the articles and topics below.';
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); search(); });
  input.addEventListener('input', search);
  const query = new URLSearchParams(location.search).get('q');
  if (query) { input.value = query; search(); }
})();
