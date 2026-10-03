// UI contract tests use an explicit bridge fixture, never simulated ASR results.
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
const root = 'src/live_subs/desktop_ui';
const server = createServer(async (request, response) => {
  const name = request.url === '/' ? 'index.html' : request.url.slice(1);
  if (!['index.html', 'style.css', 'app.js'].includes(name)) { response.writeHead(404).end(); return; }
  response.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html');
  response.end(await readFile(`${root}/${name}`));
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1060, height: 780 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    window.fixture = {
      state: 'stopped', busy: false, owned: false,
      models: [
        { kind: 'asr', repo: 'mlx-community/whisper-large-v3-turbo-4bit', ready: true, bytes: 863288426 },
        { kind: 'translation', repo: 'mlx-community/Qwen2.5-3B-Instruct-4bit', ready: true, bytes: 1803886264 },
      ],
      preferences: { language: 'en', display: 'zh-en', partials: true, fontSize: 26 }, logs: '', error: '',
    };
    window.calls = [];
    window.pywebview = { api: {
      snapshot: async () => structuredClone(window.fixture),
      get_interface: async () => ({ locale: 'zh-CN', theme: 'dark' }),
      save_interface: async value => window.calls.push(['interface', value]),
      save_preferences: async patch => { Object.assign(window.fixture.preferences, patch); window.calls.push(['preferences', patch]); },
      start_service: async () => { window.calls.push(['start']); window.fixture.state = 'starting'; window.fixture.owned = true; },
      stop_service: async () => { window.calls.push(['stop']); window.fixture.state = 'stopped'; window.fixture.owned = false; },
      prepare_models: async () => { window.calls.push(['prepare']); window.fixture.state = 'preparing'; window.fixture.owned = true; },
      copy_pairing: async () => { window.calls.push(['copy']); return { ok: true }; },
      open_resource: async name => window.calls.push(['resource', name]),
    } };
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForFunction(() => !document.querySelector('#serviceAction').disabled);
  await mkdir('.local', { recursive: true });
  await page.screenshot({ path: '.local/desktop-dark.png' });
  await page.locator('#language').selectOption('ja');
  await page.locator('#fontSize').fill('32');
  await page.waitForFunction(() => window.fixture.preferences.language === 'ja' && window.fixture.preferences.fontSize === 32);
  assert.deepEqual(await page.evaluate(() => window.calls.filter(call => call[0] === 'preferences').map(call => call[1])), [{ language: 'ja' }, { fontSize: 32 }]);
  assert.equal(await page.locator('#previewZh').evaluate(el => el.style.fontSize), '32px');
  await page.locator('#serviceAction').click();
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === '正在预热模型');
  await page.locator('#serviceAction').click();
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === '服务未启动');
  await page.evaluate(() => { window.fixture.state = 'ready'; window.fixture.owned = false; });
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === '外部服务已连接');
  assert.equal(await page.locator('#serviceAction').isDisabled(), true);
  await page.locator('[data-page="connection"]').click();
  await page.locator('#copyPairing').click();
  await page.waitForFunction(() => document.querySelector('#toast').textContent === '配对码已复制');
  await page.locator('[data-page="settings"]').click();
  await page.locator('#locale').selectOption('en');
  await page.locator('#theme').selectOption('light');
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  assert.equal(await page.locator('h1').textContent(), 'Settings');
  await page.locator('[data-page="captions"]').click();
  await page.screenshot({ path: '.local/desktop-light-en.png' });
  await page.setViewportSize({ width: 880, height: 660 });
  for (const name of ['captions', 'models', 'connection', 'settings']) {
    await page.locator(`[data-page="${name}"]`).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${name} must fit minimum window width`);
    assert.equal(await page.locator('#serviceAction').isVisible(), true);
    assert.equal(await page.locator('#serviceAction').evaluate(el => el.getBoundingClientRect().bottom <= innerHeight), true, `${name} service controls must stay in view`);
  }
  await page.evaluate(() => { window.fixture.state = 'stopped'; window.fixture.models.forEach(model => { model.ready = false; }); });
  await page.waitForFunction(() => document.querySelector('#serviceAction').textContent === 'Prepare models');
  await page.locator('#serviceAction').click();
  assert.equal(await page.locator('h1').textContent(), 'Local models');
  await page.locator('#prepare').click();
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === 'Preparing models');
  assert.equal(await page.locator('#prepare').isDisabled(), true);
  assert.deepEqual(errors, []);
  console.log('通过：桌面设置实际调用、启动/取消、外部服务保护、模型准备、配对反馈、中英切换、主题、最小窗口布局。');
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
