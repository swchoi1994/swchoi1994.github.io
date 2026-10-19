(() => {
  'use strict';
  const input = document.getElementById('post-search');
  const rows = [...document.querySelectorAll('[data-search]')];
  if (input) input.addEventListener('input', () => {
    const terms = input.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    let count = 0;
    for (const row of rows) { row.hidden = !terms.every(term => row.dataset.search.includes(term)); if (!row.hidden) count++; }
    document.getElementById('search-status').textContent = `${count}개의 글`;
    document.getElementById('no-results').hidden = count !== 0;
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('.video-load');
    if (!button || !/^[\w-]{11}$/.test(button.dataset.video)) return;
    const iframe = document.createElement('iframe');
    iframe.title = 'AI2Now YouTube 영상';
    iframe.src = `https://www.youtube-nocookie.com/embed/${button.dataset.video}`;
    iframe.allow = 'encrypted-media; picture-in-picture';
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    button.parentElement.replaceChildren(iframe);
    iframe.focus();
  });
})();
