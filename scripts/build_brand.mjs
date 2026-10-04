// Rebuild committed brand assets: npm ci && node scripts/build_brand.mjs (macOS).
// Only this development script uses Chromium; shipped apps load static resources.
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = await readFile(path.join(root, 'assets/brand/mark.svg'), 'utf8');
const shapes = source.slice(source.indexOf('>') + 1, source.lastIndexOf('</svg>'));
const tile = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none"><rect width="64" height="64" rx="17" fill="#2e4036"/>${shapes}</svg>\n`;
const app = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none"><rect x="3" y="3" width="58" height="58" rx="14" fill="#2e4036"/><g transform="translate(3 3) scale(.90625)">${shapes}</g></svg>`;
// Optical crop: the standalone mark fills 18 pt without the app tile's padding.
const mono = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="8 7 48 50" fill="none">${shapes.replaceAll('#eff1e5', '#000').replaceAll('#df9678', '#000')}</svg>`;
for (const target of ['site/icon.svg', 'src/live_subs/desktop_ui/brand.svg']) {
  await writeFile(path.join(root, target), tile);
}
const bannerPath = path.join(root, 'docs/assets/banner.svg');
const banner = await readFile(bannerPath, 'utf8');
await writeFile(bannerPath, banner.replace(
  /(<svg id="brand-mark"[^>]*>)[\s\S]*?<\/svg>/,
  `$1${shapes}</svg>`,
));
await mkdir(path.join(root, 'extension/icons'), { recursive: true });
const browser = await chromium.launch();
const temporary = await mkdtemp(path.join(tmpdir(), 'tingsub-icons-'));
try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  async function png(svg, size, target) {
    await page.setViewportSize({ width: size, height: size });
    await page.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:100vw;height:100vh}</style>${svg}`);
    await page.screenshot({ path: target, omitBackground: true });
  }
  for (const size of [16, 32, 48, 128]) {
    await png(tile, size, path.join(root, `extension/icons/icon-${size}.png`));
  }
  await png(mono, 36, path.join(root, 'src/live_subs/desktop_ui/menubar.png'));
  await png(app, 1024, path.join(root, 'assets/brand/app-icon.png'));
  if (process.platform === 'darwin') {
    const iconset = path.join(temporary, 'TingSub.iconset');
    await mkdir(iconset);
    for (const size of [16, 32, 128, 256, 512]) {
      for (const scale of [1, 2]) {
        await png(app, size * scale, path.join(iconset, `icon_${size}x${size}${scale === 2 ? '@2x' : ''}.png`));
      }
    }
    execFileSync('/usr/bin/iconutil', ['-c', 'icns', iconset, '-o', path.join(root, 'assets/brand/TingSub.icns')]);
  } else {
    console.log('macOS is required to rebuild TingSub.icns; other assets were rebuilt.');
  }
} finally {
  await browser.close();
  await rm(temporary, { recursive: true, force: true });
}
console.log('TingSub brand assets rebuilt from assets/brand/mark.svg');
