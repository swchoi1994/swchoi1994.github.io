(() => {
  'use strict';
  const root = document.documentElement;
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* private mode: the choice lasts for this page only */ } }
  };

  // Keep bookmarks to the former CV homepage and media anchor working.
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

  // Theme: the inline script in <head> already applied the saved or system choice.
  const themeButtons = [...document.querySelectorAll('[data-theme-toggle]')];
  const showTheme = () => {
    for (const button of themeButtons) button.setAttribute('aria-pressed', String(root.dataset.theme === 'dark'));
  };
  for (const button of themeButtons) {
    button.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      store.set('theme', root.dataset.theme);
      showTheme();
    });
  }
  showTheme();

  // Phone menu: the sidebar becomes a full-height sheet under the top bar.
  const menu = document.getElementById('menu-toggle');
  const sidebar = document.getElementById('sidebar');
  const setMenu = (open) => {
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    sidebar.classList.toggle('is-open', open);
    document.body.classList.toggle('menu-open', open);
  };
  if (menu && sidebar) {
    menu.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
    sidebar.addEventListener('click', (event) => { if (event.target.closest('a')) setMenu(false); });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { setMenu(false); menu.focus(); }
    });
    window.matchMedia('(min-width: 1024px)').addEventListener('change', (event) => { if (event.matches) setMenu(false); });
  }

  // Cards or list, remembered across pages.
  const setView = (view) => {
    for (const list of document.querySelectorAll('.posts[data-switchable]')) list.dataset.view = view;
    for (const button of document.querySelectorAll('[data-view-set]')) button.setAttribute('aria-pressed', String(button.dataset.viewSet === view));
  };
  for (const button of document.querySelectorAll('[data-view-set]')) {
    button.addEventListener('click', () => { setView(button.dataset.viewSet); store.set('view', button.dataset.viewSet); });
  }
  if (store.get('view') === 'list') setView('list');

  // YouTube players load only when the reader asks for one.
  document.addEventListener('click', (event) => {
    const button = event.target.closest('.video-load');
    if (!button || !/^[\w-]{11}$/.test(button.dataset.video)) return;
    const frame = document.createElement('iframe');
    frame.title = 'AI2Now YouTube video';
    frame.src = `https://www.youtube-nocookie.com/embed/${button.dataset.video}`;
    frame.allow = 'encrypted-media; picture-in-picture';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    button.parentElement.replaceChildren(frame);
    frame.focus();
  });

  // Comments (giscus) load on request and follow the page theme.
  const commentsButton = document.querySelector('[data-comments]');
  if (commentsButton) {
    commentsButton.addEventListener('click', () => {
      const script = document.createElement('script');
      script.src = 'https://giscus.app/client.js';
      script.async = true;
      script.crossOrigin = 'anonymous';
      const data = commentsButton.dataset;
      Object.assign(script.dataset, {
        repo: data.repo, repoId: data.repoId, category: data.category, categoryId: data.categoryId,
        mapping: 'pathname', strict: '1', reactionsEnabled: '1', emitMetadata: '0', inputPosition: 'top',
        theme: root.dataset.theme === 'dark' ? 'dark_dimmed' : 'light', lang: 'en'
      });
      document.getElementById('comments-thread').append(script);
      commentsButton.remove();
    }, { once: true });
  }

  // Fixed ad units, and what happens when the ad script was blocked. The owner chooses in
  // content/site.json: a wall that pauses the page (when #ad-wall is present) or a dismissible notice.
  for (const unit of document.querySelectorAll('ins.adsbygoogle')) {
    try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch { /* the unit simply stays empty */ }
  }
  const note = document.getElementById('ad-note');
  const wall = document.getElementById('ad-wall');
  // adsBlocked is set by the ad script's onerror; a loaded script sets adsbygoogle.loaded.
  const adsMissing = () => window.adsBlocked === true || !(window.adsbygoogle && window.adsbygoogle.loaded);
  // Crawlers and test browsers never load ads; they must still see the page.
  const automated = /bot|crawl|spider|slurp|preview|lighthouse|headless/i.test(navigator.userAgent);
  const showWall = () => {
    const app = document.querySelector('.app');
    wall.hidden = false;
    app.inert = true;
    app.setAttribute('aria-hidden', 'true');
    document.body.classList.add('walled');
    wall.querySelector('[data-ad-wall-reload]').focus();
  };
  if (wall) wall.querySelector('[data-ad-wall-reload]').addEventListener('click', () => location.reload());
  if (note) {
    const week = 7 * 24 * 60 * 60 * 1000;
    const dismissed = Number(store.get('adNoteDismissed')) || 0;
    const help = document.getElementById('ad-note-help');
    note.querySelector('[data-ad-note-close]').addEventListener('click', () => { note.hidden = true; store.set('adNoteDismissed', String(Date.now())); });
    note.querySelector('[data-ad-note-help]').addEventListener('click', (event) => {
      help.hidden = !help.hidden;
      event.currentTarget.setAttribute('aria-expanded', String(!help.hidden));
    });
    window.addEventListener('load', () => {
      if (automated || !navigator.onLine || !adsMissing()) return;
      // Look twice: a slow connection is not an ad blocker.
      setTimeout(() => {
        if (!adsMissing()) return;
        if (wall) showWall();
        else if (Date.now() - dismissed > week) note.hidden = false;
      }, 1500);
    });
  }

  // Archive search over the prebuilt index.
  const form = document.getElementById('search');
  if (!form) return;
  const input = document.getElementById('archive-search');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const archive = document.getElementById('archive-content');
  let index;
  let request = 0;
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
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
        const article = element('article', 'post');
        const label = element('a', 'post-label', post.topic);
        label.href = post.topic_url;
        const title = element('h2');
        const link = element('a', '', post.title);
        link.href = post.url;
        title.append(link);
        article.append(label, title, element('p', 'post-desc', post.description), element('p', 'post-meta', `${post.date} · ${post.minutes} min read`));
        results.append(article);
      }
      status.textContent = matches.length ? `${matches.length} article${matches.length === 1 ? '' : 's'} found.` : 'No matches. Try fewer words or browse a topic.';
      results.hidden = !matches.length;
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
