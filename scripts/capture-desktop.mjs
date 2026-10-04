// Capture the shipped desktop UI with explicit documentation-only sample state.
// No user settings, logs, pairing codes, audio, downloads or inference are accessed.
// Run after npm ci and npx playwright install chromium: node scripts/capture-desktop.mjs
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';

const catalog = JSON.parse(execFileSync('uv', ['run', '--frozen', 'python', '-c',
  'import json; from live_subs.catalog import CATALOG; print(json.dumps(CATALOG))'], { encoding: 'utf8' }));
const models = catalog.filter(item => item.name.includes('Turbo') || item.name.includes('3B')).map(item => ({
  kind: item.kind, repo: item.repo, ready: true, bytes: item.kind === 'asr' ? 461708984 : 1740200017,
}));
const fixture = {
  state: 'stopped', busy: false, owned: false, models,
  selection: Object.fromEntries(models.map(item => [item.kind, item.repo])),
  catalog: catalog.map(item => ({ ...item, downloaded: models.some(model => model.repo === item.repo) })),
  model_cache: '~/Library/Application Support/TingSub/model-cache',
  preferences: { translate: true, language: 'en', display: 'zh-en', partials: true, fontSize: 26 },
  download: { source: 'official', endpoint: 'https://huggingface.co' }, logs: '', error: '',
};
const server = createServer(async (request, response) => {
  const name = request.url === '/' ? 'index.html' : request.url.slice(1);
  if (!['index.html', 'style.css', 'app.js', 'brand.svg'].includes(name)) { response.writeHead(404).end(); return; }
  response.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : name.endsWith('.svg') ? 'image/svg+xml' : 'text/html');
  response.end(await readFile(`src/live_subs/desktop_ui/${name}`));
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch();
try {
  await mkdir('docs/assets/screenshots', { recursive: true });
  for (const locale of ['en', 'zh-CN']) {
    const page = await browser.newPage({ viewport: { width: 1200, height: 960 }, deviceScaleFactor: 1 });
    await page.addInitScript(({ fixture, locale }) => {
      window.pywebview = { api: {
        snapshot: async () => structuredClone(fixture),
        get_interface: async () => ({ locale, theme: 'dark' }),
      } };
    }, { fixture, locale });
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => !document.querySelector('#serviceAction').disabled);
    await page.evaluate(() => document.fonts.ready);
    // Fail the capture rather than publishing a screenshot with a broken brand image.
    await page.locator('.brand .brand-mark').evaluate(image => image.decode());
    for (const view of ['captions', 'models']) {
      await page.locator(`[data-page="${view}"]`).click();
      await page.mouse.move(1190, 20);
      await page.screenshot({ animations: 'disabled', path: `docs/assets/screenshots/${view}-${locale}.png` });
    }
    await page.close();
  }
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
