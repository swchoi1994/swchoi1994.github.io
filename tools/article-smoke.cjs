// Check every native article (or named article files) on a private ephemeral server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
let chromium;
try { ({ chromium } = require('./browser/node_modules/playwright')); }
catch { ({ chromium } = require('playwright')); }
const root = path.resolve(__dirname, '..');
const site = path.join(root, '_site');
const files = process.argv.slice(2);
const articles = (files.length ? files : fs.readdirSync(path.join(root, 'content/posts')).filter(x => x.endsWith('.html')))
  .map(x => ({ slug: path.basename(x, '.html'), text: fs.readFileSync(path.join(root, 'content/posts', path.basename(x)), 'utf8') }))
  .map(x => ({ ...x, title: JSON.parse(x.text.match(/^\s*<!--([\s\S]*?)-->/)[1]).title }));
const server = http.createServer((req, res) => {
  const file = path.resolve(site, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
  if (!file.startsWith(site + path.sep)) { res.writeHead(403).end(); return; }
  try {
    const full = fs.statSync(file).isDirectory() ? path.join(file, 'index.html') : file;
    const type = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.json': 'application/json' }[path.extname(full)];
    res.setHeader('Content-Type', type || 'application/octet-stream');
    res.end(fs.readFileSync(full));
  } catch { res.writeHead(404).end(); }
});
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    browser = await chromium.launch();
    for (const width of [390, 1360]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      for (const article of articles) {
        const response = await page.goto(`${origin}/blog/posts/${article.slug}/`);
        assert.equal(response.status(), 200, article.slug);
        assert.equal(await page.locator('h1').count(), 1, article.slug);
        assert.equal(await page.locator('h1').innerText(), article.title, article.slug);
        assert(await page.locator('h1').isVisible(), article.slug);
        assert(await page.locator('.source-box a').count() >= 2, article.slug);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${article.slug} overflows at ${width}`);
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log(`Article browser checks passed: ${articles.length} articles, mobile and desktop`);
  } finally {
    if (browser) await browser.close();
    server.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
