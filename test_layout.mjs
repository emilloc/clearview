// Run from this folder: node test_layout.mjs
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
process.env.PUPPETEER_CACHE_DIR = path.join(root, '.cache/puppeteer');
const {default: puppeteer} = await import('puppeteer');
const temp = mkdtempSync(path.join(os.tmpdir(), 'clearview-layout-'));
let browser;
try {
  copyFileSync(path.join(root, 'examples/diagram.svg'), path.join(temp, 'diagram.svg'));
  const data = {title:'Layout regression', summary:'Full-width diagrams keep their width.', sections:[], panels:[
    {title:'Full-width diagram', span:12, diagram:{path:'diagram.svg', alt:'Example job flow'}},
    ...[4,6,8].map(span => ({title:`Span ${span}`, span, steps:['A short example']}))
  ]};
  writeFileSync(path.join(temp, 'input.json'), JSON.stringify(data));
  execFileSync('python3', [path.join(root, 'render.py'), path.join(temp, 'input.json'), path.join(temp, 'output.html')]);
  browser = await puppeteer.launch({headless:'shell'});
  const page = await browser.newPage();
  await page.setOfflineMode(true);
  await page.goto(pathToFileURL(path.join(temp, 'output.html')).href);
  await page.evaluate(() => Promise.all([...document.images].map(image => image.decode())));
  for (const width of [1440,1100,1024,801,800,390]) {
    await page.setViewport({width,height:1000});
    const sizes = await page.evaluate(() => ({
      grid:document.querySelector('.panels').getBoundingClientRect().width,
      full:document.querySelector('[data-span="12"]').getBoundingClientRect().width,
      wide:document.querySelector('[data-span="8"]').getBoundingClientRect().width,
      overflow:document.documentElement.scrollWidth > innerWidth
    }));
    assert.ok(Math.abs(sizes.full - sizes.grid) < 1, `Full-width panel shrank at ${width}px`);
    if (width <= 1100) assert.ok(Math.abs(sizes.wide - sizes.grid) < 1, `Wide panel shrank at ${width}px`);
    assert.equal(sizes.overflow, false, `Horizontal overflow at ${width}px`);
  }
  const detail = JSON.parse(readFileSync(path.join(root, 'examples/detail.json'), 'utf8'));
  detail.sections[1].code = '\n  <tag>\n\t' + 'x'.repeat(200) + '  ';
  writeFileSync(path.join(temp, 'detail.json'), JSON.stringify(detail));
  execFileSync('python3', [path.join(root, 'render.py'), path.join(temp, 'detail.json'), path.join(temp, 'detail.html')]);
  await page.goto(pathToFileURL(path.join(temp, 'detail.html')).href);
  await page.locator('details:nth-of-type(1) summary').click();
  await page.locator('details:nth-of-type(2) summary').click();
  await page.locator('details:last-of-type summary').click();
  assert.equal(await page.$$eval('details[open]', items => items.length), 3);
  assert.equal(await page.$eval('pre code', element => element.textContent), detail.sections[1].code);
  assert.equal(await page.$eval('a', element => element.href), detail.sections[3].links[0].url);
  assert.equal(await page.$eval('a', element => element.getBoundingClientRect().height > 0), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  console.log('PASS: six responsive widths, independent sections, exact excerpts, and visible links.');
} finally {
  if (browser) await browser.close();
  rmSync(temp, {recursive:true, force:true});
}
