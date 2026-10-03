import { chromium } from 'playwright';
import { readFile, mkdir, mkdtemp, cp, writeFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';

await mkdir('.local', { recursive: true });
const context = await chromium.launchPersistentContext('', {
  channel: 'chromium', headless: true,
  args: [`--disable-extensions-except=${resolve('extension')}`, `--load-extension=${resolve('extension')}`],
});
try {
  const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const id = new URL(worker.url()).host;
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${id}/popup.html`);
  await popup.locator('h1').waitFor();
  assert.equal(await popup.locator('#display').inputValue(), 'zh-en');
  assert.equal(await popup.locator('#translate').isChecked(),true);
  await popup.locator('#language').selectOption('ja');
  assert.equal(await worker.evaluate(async () => (await chrome.storage.local.get('language')).language), 'ja');
  await popup.screenshot({ path: '.local/popup.png' });
  // Explicit preference protocol fixture; real endpoint auth is checked in Python.
  await worker.evaluate(() => {
    globalThis.preferencePatches = [];
    globalThis.preferenceMigrations = [];
    const originalFetch = fetch;
    globalThis.fetch = async (url, options) => {
      if (url.endsWith('/preferences/initialize') && options.method === 'POST') {
        globalThis.preferenceMigrations.push(JSON.parse(options.body));
        return new Response('{}', { status: 200 });
      }
      if (url.endsWith('/preferences') && options.method === 'PATCH') {
        globalThis.preferencePatches.push(JSON.parse(options.body));
        return new Response('{}', { status: 200 });
      }
      return originalFetch(url, options);
    };
  });
  await popup.route('http://127.0.0.1:18765/preferences', async route => {
    assert.equal(route.request().headers().authorization, 'Bearer ui-test-pairing');
    await route.fulfill({ json: { language: 'en', display: 'source-zh', partials: false, fontSize: 30 } });
  });
  await popup.locator('details').evaluate(el => { el.open = true; });
  await popup.locator('#token').fill('ui-test-pairing');
  await popup.locator('#token').blur();
  await popup.waitForFunction(() => document.querySelector('#fontSize').value === '30');
  assert.deepEqual(await worker.evaluate(() => globalThis.preferenceMigrations), [{ language: 'ja', display: 'zh-en', translate: true, partials: true, fontSize: 26 }]);
  assert.equal(await popup.locator('#display').inputValue(), 'source-zh');
  assert.equal(await popup.locator('#partials').isChecked(), false);
  await popup.locator('#language').selectOption('ja');
  await popup.waitForFunction(async () => (await chrome.storage.local.get('language')).language === 'ja');
  await popup.waitForFunction(() => document.querySelector('#language').value === 'ja');
  await popup.waitForFunction(async () => !(await chrome.storage.local.get('pendingPreferences')).pendingPreferences);
  assert.deepEqual(await worker.evaluate(() => globalThis.preferencePatches), [{ language: 'ja' }]);


  await popup.locator('#translate').uncheck();
  await popup.waitForFunction(async ()=>(await chrome.storage.local.get('translate')).translate === false);
  assert.equal(await popup.locator('#display').isDisabled(),true);
  await popup.reload();
  assert.equal(await popup.locator('#translate').isChecked(),false,'旧服务未返回新字段时也应保留用户开关');

  // The renderer is exercised with explicit protocol fixtures, not claimed as ASR output.
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.setContent('<html><body style="background:#18252f;color:white;font:24px system-ui;padding:80px"><h1>字幕渲染测试页</h1><p>以下内容为协议测试数据，不代表模型识别结果。</p><div id="player" style="height:500px;background:#243945"></div></body></html>');
  await page.evaluate(() => {
    window.chrome = { runtime: { onMessage: { addListener: callback => { window.receive = callback; } }, sendMessage: async () => ({}) } };
  });
  await page.addScriptTag({ content: await readFile('extension/overlay.js', 'utf8') });
  const send = event => page.evaluate(event => window.receive({ target: 'overlay', event }), event);
  await send({ type: 'reset', fontSize: 26 });
  await send({ type: 'state', state: 'running', message: '渲染测试 · 协议数据' });
  await send({ type: 'transcript', id: 1, source: '今日は新しい技術について話します。', language: 'ja', final: false, display: 'zh-en' });
  assert.match(await page.locator('.row .note').textContent(), /识别中/);
  await send({ type: 'translation_progress', id: 1, zh: '今天我们来聊一聊新技术。', en: '', final: true, speech_start_ms: Date.now() - 3200 });
  assert.equal(await page.locator('.zh').textContent(), '今天我们来聊一聊新技术。');
  assert.equal(await page.locator('.row .note').textContent(), '');
  assert.equal(await page.locator('.diagnostics').isVisible(), false);
  assert.match(await page.locator('.state').textContent(), /首个中文/);
  await send({ type: 'translation', id: 1, source: '今日は新しい技術について話します。', zh: '今天我们来聊一聊新技术。', en: 'Today we will talk about new technology.', final: true, display: 'zh-en', speech_end_ms: Date.now() - 900, asr_ms: 320, translation_ms: 260 });
  await send({ type: 'transcript', id: 1, source: 'obsolete draft', final: false });
  await send({ type: 'translation_progress', id: 1, zh: 'obsolete partial Chinese', final: true });
  assert.equal(await page.locator('.zh').textContent(), '今天我们来聊一聊新技术。');
  assert.equal(await page.locator('.second').textContent(), 'Today we will talk about new technology.');
  await page.screenshot({ path: '.local/overlay.png' });

  // Same-language text is displayed once; Chinese is not duplicated while English is pending.
  await send({type:'reset'});
  await send({type:'translation_progress',id:1,source:'保留中文原句。',language:'zh',display:'zh-en',zh:'保留中文原句。',en:'',final:true});
  assert.equal(await page.locator('.second').isVisible(),false);
  assert.equal(await page.locator('.note').textContent(),'正在翻译英文…');
  await send({type:'translation',id:1,source:'保留中文原句。',language:'zh',display:'zh-en',zh:'保留中文原句。',en:'Keep the original Chinese.',final:true});
  assert.equal(await page.locator('.second').isVisible(),true);
  await send({type:'reset'});
  await send({type:'translation',id:1,source:'原文就是中文。',language:'zh',display:'source-zh',zh:'原文就是中文。',en:'',final:true});
  assert.equal(await page.locator('.zh').textContent(),'原文就是中文。');
  assert.equal(await page.locator('.second').isVisible(),false);
  await send({type:'reset'});
  await send({type:'translation',id:1,source:'今日は新しい技術について話します。',language:'ja',display:'zh-en',zh:'今天我们来聊一聊新技术。',en:'Today we will talk about new technology.',final:true});

  await send({type:'reset'});
  await send({type:'transcript',id:1,source:'原文草稿',translate:false,final:false});
  assert.equal(await page.locator('.zh').textContent(),'原文草稿');
  assert.equal(await page.locator('.second').isVisible(),false);
  await send({type:'translation',id:1,source:'Keep the original words.',translate:false,final:true,translation_ms:0});
  assert.equal(await page.locator('.zh').textContent(),'Keep the original words.');
  assert.equal(await page.locator('.note').textContent(),'');
  assert.equal(await page.locator('.second').isVisible(),false);
  await send({type:'reset'});
  await send({type:'translation',id:1,source:'今日は新しい技術について話します。',language:'ja',display:'zh-en',zh:'今天我们来聊一聊新技术。',en:'Today we will talk about new technology.',final:true});

  const stableRow = await page.locator('.row').elementHandle();
  await send({ type: 'transcript', id: 2, source: '<img src=x onerror="window.pwned=true">', final: true });
  assert.equal(await page.locator('.zh').textContent(), '今天我们来聊一聊新技术。');
  assert.match(await page.locator('.draft').textContent(), /<img/);
  assert.equal(await stableRow.evaluate(el => el.isConnected), true);
  assert.equal(await page.locator('#tingqiao-local-captions img').count(), 0);
  assert.equal(await page.evaluate(() => Boolean(window.pwned)), false);
  await send({ type: 'transcript', id: 3, source: 'new sentence', final: true });
  assert.equal(await page.locator('.row').count(), 1);
  assert.equal(await page.locator('.second').textContent(), 'new sentence');
  await send({ type: 'translation', id: 1, zh: 'late old result', final: true });
  assert.equal(await page.locator('.row[data-id="1"]').count(), 0);
  await send({ type: 'error', id: 3, message: '本地模型失败' });
  assert.match(await page.locator('.row[data-id="3"] .note').textContent(), /翻译失败/);
  await send({ type: 'rejected', id: 4, reason: 'low_confidence', message: '已跳过片段：识别置信度低', metrics: { counts: { translated: 1, low_confidence: 1 } } });
  assert.match(await page.locator('.stats').textContent(), /低置信度 1/);
  await page.locator('#player').click();
  await page.evaluate(() => document.querySelector('#player').requestFullscreen());
  await page.waitForFunction(() => document.querySelector('#tingqiao-local-captions').parentElement.id === 'player');
  assert.equal(await page.evaluate(() => document.querySelector('#tingqiao-local-captions').parentElement.id), 'player');
  console.log('通过：真实 Chromium 加载插件、设置持久化、双语渲染、过期草稿、历史上限、XSS文本、错误提示、全屏字幕。');
} finally { await context.close(); }


// Use a separate Chromium profile to verify Chrome's real path-derived ID and
// durable storage across an App export update, without touching user Chrome.
const updateRoot = await mkdtemp(resolve('.local/extension-update-'));
let updatedContext;
try {
  const bundle = resolve(updateRoot, 'bundle');
  const data = resolve(updateRoot, 'data');
  const profile = resolve(updateRoot, 'profile');
  await cp('extension', resolve(bundle, 'extension'), {recursive:true});
  const exportExtension = () => execFileSync('python3', ['-c',
    'import sys; sys.path.insert(0, "src"); from pathlib import Path; from live_subs.runtime import install_extension; sys.frozen=True; sys._MEIPASS=sys.argv[1]; print(install_extension(Path(sys.argv[2])))',
    bundle, data], {encoding:'utf8'}).trim();
  const firstPath = exportExtension();
  const launch = path => chromium.launchPersistentContext(profile, {
    channel:'chromium', headless:true,
    args:[`--disable-extensions-except=${path}`, `--load-extension=${path}`],
  });
  updatedContext = await launch(firstPath);
  let worker = updatedContext.serviceWorkers()[0] || await updatedContext.waitForEvent('serviceworker');
  const originalId = new URL(worker.url()).host;
  await worker.evaluate(() => chrome.storage.local.set({token:'fixture-pairing',language:'ja',translate:false}));
  await updatedContext.close();
  updatedContext = null;
  const manifestPath = resolve(bundle, 'extension/manifest.json');
  const manifest = JSON.parse(await readFile(manifestPath,'utf8'));
  manifest.version = '0.1.1';
  await writeFile(manifestPath, JSON.stringify(manifest));
  const secondPath = exportExtension();
  assert.equal(secondPath,firstPath,'替换 App 导出内容后，已安装插件的路径保持不变');
  updatedContext = await launch(secondPath);
  worker = updatedContext.serviceWorkers()[0] || await updatedContext.waitForEvent('serviceworker');
  assert.equal(new URL(worker.url()).host,originalId,'更新后 Chrome 保留同一插件 ID');
  assert.equal(await worker.evaluate(()=>chrome.runtime.getManifest().version),'0.1.1','重新加载后必须执行更新后的插件');
  assert.deepEqual(await worker.evaluate(()=>chrome.storage.local.get(['token','language','translate'])),{
    token:'fixture-pairing',language:'ja',translate:false,
  },'更新插件不丢失配对码和用户设置');
  console.log('通过：实际 Chrome 插件更新保留 ID、配对和偏好，并加载新版本。');
} finally {
  await updatedContext?.close();
  await rm(updateRoot,{recursive:true,force:true});
}
