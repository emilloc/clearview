// Run from this folder: node test_layout.mjs
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {copyFileSync, mkdtempSync, rmSync, writeFileSync} from 'node:fs';
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
  console.log('PASS: six responsive widths without horizontal overflow.');
} finally {
  if (browser) await browser.close();
  rmSync(temp, {recursive:true, force:true});
}
