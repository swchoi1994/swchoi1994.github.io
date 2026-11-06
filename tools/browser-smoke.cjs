// Optional browser proof: serve _site on port 8791; requires an installed @playwright/test.
const { chromium, expect } = require('@playwright/test');
const assert = require('node:assert/strict');
require('node:fs').mkdirSync('output', { recursive: true });
(async () => {
 const browser = await chromium.launch({channel:'chrome',headless:true});
 const context = await browser.newContext({viewport:{width:1440,height:1000}});
 const errors=[];
 await context.route('**/*', route => route.request().url().startsWith('http://127.0.0.1:8791') || /fonts\.(googleapis|gstatic)\.com/.test(route.request().url()) ? route.continue() : route.abort());
 const page = await context.newPage();
 page.on('pageerror', e => errors.push(e.message));
 const origin='http://127.0.0.1:8791';
 for(const path of ['/', '/topics/','/topics/windows/','/guides/','/blog/','/blog/page/2/','/blog/posts/naver-224467696426/','/blog/posts/naver-224458565730/','/blog/posts/naver-224467587320/','/blog/about/','/portfolio/']) {
   const response=await page.goto(origin+path);
   assert.equal(response.status(),200,path);
   await expect(page.locator('h1')).toHaveCount(1);
   for (const img of await page.locator('.story-image img, .article-cover img, .article-reference img').all()) {
     await img.scrollIntoViewIfNeeded();
     await expect.poll(() => img.evaluate(el => el.complete && el.naturalWidth > 0)).toBeTruthy();
   }
   for(const width of [1440,390]) {
     await page.setViewportSize({width,height:900});
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow: ${path} at ${width}`);
   }
 }
 await page.goto(origin+'/blog/');
 await page.locator('#archive-search').fill('COUNTIF');
 await expect(page.locator('#search-results')).toBeVisible();
 await expect(page.locator('#search-results h3')).toHaveCount(1);
 await expect(page.locator('#search-results')).toContainText('COUNTIF');
 const searchImage = page.locator('#search-results img');
 await searchImage.scrollIntoViewIfNeeded();
 await expect.poll(() => searchImage.evaluate(el => el.complete && el.naturalWidth > 0)).toBeTruthy();
 await page.locator('#archive-search').fill('qwerty-no-matches');
 await expect(page.locator('#search-status')).toContainText('No matches');
 await page.locator('#archive-search').fill('');
 await expect(page.locator('#archive-content')).toBeVisible();
 await page.goto(origin+'/blog/?q=COUNTIF');
 await expect(page.locator('#search-results h3')).toHaveCount(1);
 await page.goto(origin+'/');
 await page.locator('.nav-toggle').click();
 await expect(page.locator('.nav-toggle')).toHaveAttribute('aria-expanded','true');
 await expect(page.locator('.nav-menu')).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.locator('.nav-toggle')).toHaveAttribute('aria-expanded','false');
 for (const width of [1440,390]) {
   await page.setViewportSize({width,height:1000});
   for (const img of await page.locator('.story-image img').all()) {
     await img.scrollIntoViewIfNeeded();
     await expect.poll(() => img.evaluate(el => el.complete && el.naturalWidth > 0)).toBeTruthy();
   }
   await page.evaluate(() => scrollTo(0, 0));
   await page.screenshot({path:`output/images-home-${width}.png`,fullPage:true});
 }
 await page.goto(origin+'/#work');
 await expect(page).toHaveURL(origin+'/portfolio/#work');
 await page.goto(origin+'/blog/#media');
 await expect(page).toHaveURL(origin+'/videos/');
 await page.locator('.video-load').first().click();
 await expect(page.locator('iframe')).toHaveCount(1);
 await page.goto(origin+'/blog/posts/naver-224467696426/');
 await expect(page.locator('a[href="/blog/posts/naver-224466093515/"]')).toBeVisible();
 await expect(page.locator('.article-cover')).toBeVisible();
 await expect(page.locator('.article-cover figcaption')).toContainText('AI-generated editorial illustration');
 await page.screenshot({path:'output/journal-article-mobile.png',fullPage:true});
 const failure=await context.newPage();
 await failure.route('**/search-index.json',route=>route.abort());
 await failure.goto(origin+'/blog/');
 await failure.locator('#archive-search').fill('test');
 await expect(failure.locator('#search-status')).toContainText('temporarily unavailable');
 await expect(failure.locator('#archive-content')).toBeVisible();
 const noJS=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
 const fallback=await noJS.newPage();
 await fallback.goto(origin+'/blog/');
 await expect(fallback.locator('.nav-menu a[href="/topics/"]')).toBeVisible();
 await expect(fallback.locator('.pagination a')).toHaveCount(11);
 assert.deepEqual(errors,[]);
 await noJS.close();
 await context.close();
 await browser.close();
 console.log('PASS: loaded cover/card/search images, desktop/mobile overflow, navigation, all-archive search, empty/error states, legacy URLs, video activation, English links, no-JS navigation and pagination; no application JS errors.');
})().then(()=>process.exit(0)).catch(error=>{console.error(error);process.exit(1);});
