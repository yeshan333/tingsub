import { chromium } from 'playwright';
import { readFile, mkdir } from 'node:fs/promises';
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
  await popup.locator('#language').selectOption('ja');
  assert.equal(await worker.evaluate(async () => (await chrome.storage.local.get('language')).language), 'ja');
  await popup.screenshot({ path: '.local/popup.png' });

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
  assert.match(await page.locator('.row .note').textContent(), /识别草稿/);
  await send({ type: 'translation_progress', id: 1, zh: '今天我们来聊一聊新技术。', en: '', final: true, speech_start_ms: Date.now() - 3200 });
  assert.equal(await page.locator('.zh').textContent(), '今天我们来聊一聊新技术。');
  assert.match(await page.locator('.row .note').textContent(), /中文先行/);
  assert.match(await page.locator('.state').textContent(), /首个中文/);
  await send({ type: 'translation', id: 1, source: '今日は新しい技術について話します。', zh: '今天我们来聊一聊新技术。', en: 'Today we will talk about new technology.', final: true, display: 'zh-en', speech_end_ms: Date.now() - 900, asr_ms: 320, translation_ms: 260 });
  await send({ type: 'transcript', id: 1, source: 'obsolete draft', final: false });
  await send({ type: 'translation_progress', id: 1, zh: 'obsolete partial Chinese', final: true });
  assert.equal(await page.locator('.zh').textContent(), '今天我们来聊一聊新技术。');
  assert.equal(await page.locator('.second').textContent(), 'Today we will talk about new technology.');
  await page.screenshot({ path: '.local/overlay.png' });

  await send({ type: 'transcript', id: 2, source: '<img src=x onerror="window.pwned=true">', final: true });
  assert.equal(await page.locator('#tingqiao-local-captions img').count(), 0);
  assert.equal(await page.evaluate(() => Boolean(window.pwned)), false);
  await send({ type: 'transcript', id: 3, source: 'new sentence', final: true });
  assert.equal(await page.locator('.row').count(), 2);
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
