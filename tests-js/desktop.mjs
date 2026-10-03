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
      preferences: { translate: true, language: 'en', display: 'zh-en', partials: true, fontSize: 26 }, logs: '', error: '',
    };
    window.fixture.selection = Object.fromEntries(window.fixture.models.map(model => [model.kind, model.repo]));
    window.fixture.catalog = [
      ...window.fixture.models.map(model => ({ ...model, name: model.repo, downloaded: true, description: {} })),
      { kind: 'asr', repo: 'mlx-community/whisper-small-mlx-4bit', name: 'Whisper Small', description: {} },
      { kind: 'translation', repo: 'mlx-community/Qwen2.5-1.5B-Instruct-4bit', name: 'Qwen 1.5B', description: {} },
    ];
    window.calls = [];
    window.pywebview = { api: {
      snapshot: async () => structuredClone(window.fixture),
      get_interface: async () => ({ locale: 'zh-CN', theme: 'dark' }),
      save_interface: async value => { await new Promise(resolve => setTimeout(resolve, 150)); window.calls.push(['interface', value]); },
      save_preferences: async patch => { Object.assign(window.fixture.preferences, patch); window.calls.push(['preferences', patch]); },
      start_service: async () => { window.calls.push(['start']); window.fixture.state = 'starting'; window.fixture.owned = true; },
      stop_service: async () => { window.calls.push(['stop']); window.fixture.state = 'stopped'; window.fixture.owned = false; },
      prepare_models: async (selection, download) => { window.calls.push(['prepare', selection, download]); window.fixture.state = 'preparing'; window.fixture.owned = true; },
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
  await page.locator('#translate').uncheck();
  await page.waitForFunction(()=>window.fixture.preferences.translate === false);
  assert.equal(await page.locator('#display').isDisabled(),true);
  assert.equal(await page.locator('#previewEn').isVisible(),false);
  assert.equal(await page.locator('#previewZh').textContent(),'世界は広い。ゆっくり耳を傾けよう。');
  await page.locator('#translate').check();
  await page.waitForFunction(()=>window.fixture.preferences.translate === true);
  assert.equal(await page.locator('#display').isEnabled(),true);
  await page.locator('#serviceAction').click();
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === '正在预热模型');
  await page.locator('#serviceAction').click();
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === '服务未启动');
  await page.evaluate(() => { window.fixture.state = 'ready'; window.fixture.owned = false; });
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === '外部服务已连接');
  assert.equal(await page.locator('#serviceAction').isDisabled(), true);
  await page.locator('[data-page="models"]').click();
  for (const busy of [false,true]) {
    await page.evaluate(busy=>{window.fixture.busy=busy;},busy);
    await page.locator('#asrModel').selectOption('mlx-community/whisper-small-mlx-4bit');
    await page.locator('#translationModel').selectOption('mlx-community/Qwen2.5-1.5B-Instruct-4bit');
    await page.waitForTimeout(1700);
    assert.equal(await page.locator('#asrModel').isEnabled(),true,'服务空闲或生成字幕时都可浏览模型');
    assert.equal(await page.locator('#translationModel').inputValue(),'mlx-community/Qwen2.5-1.5B-Instruct-4bit');
    assert.equal(await page.locator('#downloadSource').isEnabled(),true);
    assert.equal(await page.locator('#prepare').isDisabled(),true,'浏览选择不能切换运行中的模型');
    assert.equal(await page.locator('#prepare').textContent(),'停止服务后应用');
    assert.equal(await page.evaluate(()=>window.fixture.selection.translation),'mlx-community/Qwen2.5-3B-Instruct-4bit');
    assert.equal(await page.evaluate(()=>window.calls.filter(call=>call[0]==='prepare').length),0);
  }
  await page.evaluate(()=>{window.fixture.busy=false;});
  await page.locator('[data-page="connection"]').click();
  await page.locator('#copyPairing').click();
  await page.waitForFunction(() => document.querySelector('#toast').textContent === '配对码已复制');
  await page.locator('[data-page="settings"]').click();
  await page.locator('#locale').selectOption('en');
  await page.locator('#theme').selectOption('light');
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  assert.equal(await page.locator('h1').textContent(), 'Settings');
  await page.waitForFunction(() => window.calls.filter(call => call[0] === 'interface').length === 2);
  assert.deepEqual(await page.evaluate(() => window.calls.filter(call => call[0] === 'interface').at(-1)[1]), { locale: 'en', theme: 'light' });
  await page.locator('[data-page="captions"]').click();
  await page.screenshot({ path: '.local/desktop-light-en.png' });
  await page.setViewportSize({ width: 880, height: 660 });
  for (const name of ['captions', 'models', 'connection', 'settings']) {
    await page.locator(`[data-page="${name}"]`).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${name} must fit minimum window width`);
    assert.equal(await page.locator('#serviceAction').isVisible(), true);
    assert.equal(await page.locator('#serviceAction').evaluate(el => el.getBoundingClientRect().bottom <= innerHeight), true, `${name} service controls must stay in view`);
  }
  await page.evaluate(() => { window.fixture.state = 'stopped'; });
  await page.locator('[data-page="models"]').click();
  assert.equal(await page.locator('.logs').getAttribute('open'),null);
  await page.getByRole('button',{name:'Show log file in Finder'}).click();
  assert.equal(await page.evaluate(()=>window.calls.some(call=>call[0]==='resource' && call[1]==='logs')),true);
  assert.equal(await page.locator('.logs').getAttribute('open'),null,'定位日志不应意外展开日志正文');
  await page.waitForFunction(() => !document.querySelector('#translationModel').disabled);
  await page.locator('#asrModel').selectOption('mlx-community/whisper-small-mlx-4bit');
  await page.locator('#translationModel').selectOption('mlx-community/Qwen2.5-1.5B-Instruct-4bit');
  await page.waitForTimeout(1700); // One real refresh must not overwrite an unsubmitted choice.
  assert.equal(await page.locator('#translationModel').inputValue(), 'mlx-community/Qwen2.5-1.5B-Instruct-4bit');
  assert.match(await page.locator('[data-i18n=downloadSourceHint]').textContent(), /community mirror/);
  await page.locator('#downloadSource').selectOption('custom');
  await page.locator('#downloadEndpoint').fill('https://models.example');
  await page.screenshot({ path: '.local/desktop-models-en.png' });
  await page.locator('#prepare').click();
  assert.deepEqual(await page.evaluate(() => window.calls.filter(call => call[0] === 'prepare').at(-1)[1]), {
    asr: 'mlx-community/whisper-small-mlx-4bit', translation: 'mlx-community/Qwen2.5-1.5B-Instruct-4bit',
  });
  assert.equal(await page.locator('#translationModel').isDisabled(), true);
  assert.deepEqual(await page.evaluate(() => window.calls.filter(call => call[0] === 'prepare').at(-1)[2]), {source:'custom', endpoint:'https://models.example'});
  await page.evaluate(() => { window.fixture.preparation = {stage:'download', bytes:52428800, total_bytes:209715200, index:1, count:2, repo:'Whisper Small'}; });
  await page.waitForFunction(() => document.querySelector('#modelProgress').value === 25);
  assert.equal(await page.locator('#downloadBytes').textContent(), '25% · 50.0 MB / 200.0 MB');
  assert.equal(await page.locator('#downloadSource').isDisabled(), true);
  await page.screenshot({path:'.local/desktop-download-progress.png'});
  await page.evaluate(() => { window.fixture.preparation = {stage:'validate'}; });
  await page.waitForFunction(() => document.querySelector('#preparationStatus').textContent.includes('validating'));
  assert.equal(await page.locator('#modelProgress').getAttribute('value'), null, '加载校验必须使用阶段提示，不能显示虚构百分比');
  assert.equal(await page.locator('#downloadBytes').textContent(), '');
  await page.evaluate(() => { window.fixture.state = 'error'; window.fixture.owned = false; window.fixture.preparation = { stage: 'error' }; });
  await page.waitForFunction(() => document.querySelector('#preparationStatus').textContent.includes('unchanged'));
  assert.equal(await page.locator('#prepare').isEnabled(), true, 'Failed switch can be retried');
  assert.equal(await page.evaluate(() => window.fixture.selection.translation), 'mlx-community/Qwen2.5-3B-Instruct-4bit');
  await page.evaluate(() => { window.fixture.state = 'stopped'; window.fixture.models.forEach(model => { model.ready = false; }); });
  await page.waitForFunction(() => document.querySelector('#serviceAction').textContent === 'Prepare models');
  assert.equal(await page.locator('#welcome').isVisible(), true);
  await page.locator('#serviceAction').click();
  assert.equal(await page.locator('h1').textContent(), 'Local models');
  await page.locator('#prepare').click();
  await page.waitForFunction(() => document.querySelector('#serviceTitle').textContent === 'Preparing models');
  assert.equal(await page.locator('#prepare').isDisabled(), true);
  assert.deepEqual(errors, []);
  console.log('通过：桌面设置实际调用、启动/取消、外部服务保护、模型准备、配对反馈、中英切换、主题、最小窗口布局。');
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
