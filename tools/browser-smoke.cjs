// Optional browser proof: serve _site on port 8791; requires an installed Playwright.
//   python3 -m http.server 8791 --directory _site & node tools/browser-smoke.cjs
const assert = require('node:assert/strict');
let chromium;
try { ({ chromium } = require('@playwright/test')); } catch { ({ chromium } = require('playwright')); }

(async () => {
  const browser = await chromium.launch();
  const origin = 'http://127.0.0.1:8791';
  // Never let a test run reach the outside world: analytics would count it as a visit and the ad
  // script would request ads. Only the local site and the web fonts are allowed through.
  const offline = async (options) => {
    const created = await browser.newContext(options);
    await created.route('**/*', route => {
      const url = route.request().url();
      return url.startsWith(origin) || /^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(url) ? route.continue() : route.abort();
    });
    return created;
  };
  const context = await offline({ viewport: { width: 1360, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));

  // Every page type renders once, with one heading and no sideways scroll at any width.
  const paths = ['/', '/topics/', '/topics/windows/', '/guides/', '/guides/ai-coding-agent-repos/', '/blog/', '/blog/page/2/', '/videos/',
    '/blog/posts/naver-224467696426/', '/blog/posts/naver-224444722682/', '/blog/posts/claude-code-project-setup/', '/blog/posts/dockerfile-checklist/', '/blog/posts/vllm-first-server/', '/blog/posts/deepseek-api-guide/', '/blog/posts/zai-glm-coding-plan-guide/', '/series/', '/series/vllm-server/', '/projects/', '/blog/posts/vllm-phind-codellama-a100/', '/blog/posts/vllm-monitoring-prometheus-grafana/', '/blog/posts/vllm-multi-user-serving/', '/blog/posts/mac-mini-personal-ai-assistant/', '/blog/posts/ai-coding-agent-tips/', '/blog/posts/naver-224467587320/', '/blog/about/', '/blog/privacy/', '/portfolio/'];
  for (const width of [390, 768, 1024, 1360, 1680]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of paths) {
      const response = await page.goto(origin + path);
      assert.equal(response.status(), 200, path);
      assert.equal(await page.locator('h1').count(), 1, `one h1: ${path}`);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow: ${path} at ${width}`);
    }
  }
  await page.setViewportSize({ width: 1360, height: 900 });

  // Dark mode and the cards/list choice persist between pages.
  await page.goto(origin + '/');
  await page.click('.page-head [data-theme-toggle]');
  assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
  await page.click('[data-view-set=list]');
  await page.goto(origin + '/topics/windows/');
  assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
  assert.equal(await page.getAttribute('.posts[data-switchable]', 'data-view'), 'list');
  await page.click('.page-head [data-theme-toggle]');
  await page.click('[data-view-set=cards]');

  // Search: live on the archive, and from the home page search box.
  await page.goto(origin + '/blog/');
  await page.fill('#archive-search', 'COUNTIF');
  await page.waitForSelector('#search-results:not([hidden])');
  assert.equal(await page.locator('#search-results .post').count(), 1);
  await page.fill('#archive-search', 'qwerty-no-matches');
  await page.waitForFunction(() => document.getElementById('search-status').textContent.includes('No matches'));
  await page.fill('#archive-search', '');
  assert(await page.isVisible('#archive-content'));
  await page.goto(origin + '/');
  await page.fill('.search input', 'Gmail');
  await page.press('.search input', 'Enter');
  await page.waitForSelector('#search-results:not([hidden])');

  // Old bookmarks still land somewhere useful; players load on request.
  await page.goto(origin + '/#work');
  await page.waitForURL(origin + '/portfolio/#work');
  await page.goto(origin + '/blog/#media');
  await page.waitForURL(origin + '/videos/');
  await page.click('.video-load >> nth=0');
  assert.equal(await page.locator('.video-space iframe').count(), 1);

  // Phone menu opens under the top bar and closes with Escape.
  const phone = await (await offline({ viewport: { width: 390, height: 844 } })).newPage();
  await phone.goto(origin + '/');
  await phone.click('#menu-toggle');
  assert.equal(await phone.evaluate(() => document.getElementById('sidebar').getBoundingClientRect().top), 56);
  await phone.keyboard.press('Escape');
  assert.equal(await phone.getAttribute('#menu-toggle', 'aria-expanded'), 'false');

  // With the ad script blocked, a real reader's browser gets the wall (the owner's "adblock_wall"
  // setting) and the page behind it is paused. Test browsers above identify as headless and are spared.
  const person = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
  const reader = await (await offline({ viewport: { width: 1360, height: 900 }, userAgent: person })).newPage();
  await reader.goto(origin + '/blog/posts/naver-224444722682/', { waitUntil: 'load' });
  await reader.waitForSelector('#ad-wall:not([hidden])', { timeout: 6000 });
  assert.equal(await reader.evaluate(() => document.querySelector('.app').inert), true);
  assert.equal(await reader.evaluate(() => document.activeElement.hasAttribute('data-ad-wall-reload')), true);
  // The pages that carry no ads carry no wall, so a reader can always reach contact and privacy.
  await reader.goto(origin + '/blog/contact/', { waitUntil: 'load' });
  await reader.waitForTimeout(2200);
  assert.equal(await reader.locator('#ad-wall').count(), 0);

  assert.deepEqual(errors, []);
  await browser.close();
  console.log('browser smoke ok');
})().catch(error => { console.error(error); process.exit(1); });
