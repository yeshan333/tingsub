// End-to-end: actual tabCapture + AudioWorklet + local GPU models + rendered captions.
// Requires a running service and .local/benchmark/{en,ja}.wav (benchmark.py creates them).
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const token = (await readFile('.local/token', 'utf8')).trim();
const en = await readFile('.local/benchmark/en.wav');
const ja = await readFile('.local/benchmark/ja.wav');
const server = createServer((request, response) => {
  if (request.url === '/en.wav' || request.url === '/ja.wav') {
    response.writeHead(200, { 'Content-Type': 'audio/wav' });
    response.end(request.url === '/en.wav' ? en : ja);
  } else {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    response.end('<html lang="zh-CN"><body style="background:#1e3038;color:white;padding:70px;font:24px system-ui"><h1>听桥 · 真实音频端到端测试</h1><p>本页播放本机合成的语音，由插件直接采集标签页音频。</p><audio controls id="audio"></audio></body></html>');
  }
});
await new Promise(resolve => server.listen(8899, '127.0.0.1', resolve));
const context = await chromium.launchPersistentContext('', {
  channel: 'chromium', headless: true,
  ignoreDefaultArgs: ['--mute-audio'],
  args: ['--enable-unsafe-extension-debugging', '--autoplay-policy=no-user-gesture-required',
    `--disable-extensions-except=${resolve('extension')}`, `--load-extension=${resolve('extension')}`],
});
try {
  const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const id = new URL(worker.url()).host;
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('http://127.0.0.1:8899');
  const browserCDP = await context.browser().newBrowserCDPSession();
  const { targetInfos } = await browserCDP.send('Target.getTargets', { filter: [{ type: 'tab' }] });
  const tabTarget = targetInfos.find(target => target.url === 'http://127.0.0.1:8899/');
  assert.ok(tabTarget, JSON.stringify(targetInfos));
  await worker.evaluate(() => {
    globalThis.captureEvents = [];
    chrome.runtime.onMessage.addListener(message => {
      if (message.type === 'event') captureEvents.push({ ...message.event,
        received_ms: Date.now(),
        end_to_end_ms: message.event.speech_end_ms ? Math.round(Date.now() - message.event.speech_end_ms) : undefined,
      });
    });
  });
  const results = [];
  let control;
  for (const language of ['en', 'ja']) {
    await worker.evaluate(async settings => { await chrome.storage.local.set(settings); captureEvents = []; }, {
      token, language, display: 'zh-en', partials: true, fontSize: 26,
    });
    await page.bringToFront();
    await browserCDP.send('Extensions.triggerAction', { id, targetId: tabTarget.targetId });
    // Native toolbar popups aren't Playwright Page targets. Invoke the same public
    // message API from an extension page, after the real action grants activeTab.
    if (!control) {
      control = await context.newPage();
      await control.goto(`chrome-extension://${id}/popup.html`);
    }
    const tabs = await worker.evaluate(() => chrome.tabs.query({}));
    const fixtureTab = tabs.find(tab => tab.url === 'http://127.0.0.1:8899/');
    assert.ok(fixtureTab);
    const result = await control.evaluate(tabId => chrome.runtime.sendMessage({ target: 'background', type: 'start', tabId }), fixtureTab.id);
    assert.equal(result.ok, true, JSON.stringify(result));
    try {
      await page.waitForFunction(() => document.getElementById('tingqiao-local-captions')?.shadowRoot.querySelector('.state').textContent.includes('正在聆听'), null, { timeout: 15000 });
    } catch (error) {
      throw new Error(`采集未启动：${await control.locator('#status').textContent()}`, { cause: error });
    }
    await page.evaluate(async language => {
      const audio = document.getElementById('audio'); audio.src = `/${language}.wav`; await audio.play();
    }, language);
    await page.waitForFunction(() => document.getElementById('audio').ended, null, { timeout: 30000 });
    const audioStatus = await worker.evaluate(() => chrome.runtime.sendMessage({ target: 'offscreen', type: 'status' }));
    // Stop drains the final utterance. Do not replace inference with protocol fixtures.
    await control.evaluate(() => chrome.runtime.sendMessage({ target: 'background', type: 'stop' }));
    const deadline = Date.now() + 45000;
    let status;
    do {
      status = await worker.evaluate(() => chrome.runtime.sendMessage({ target: 'offscreen', type: 'status' }));
      if (status.state === 'idle' || status.state === 'error') break;
      await new Promise(resolve => setTimeout(resolve, 200));
    } while (Date.now() < deadline);
    assert.equal(status.state, 'idle', JSON.stringify(status));
    const events = await worker.evaluate(() => captureEvents);
    const translations = events.filter(event => event.type === 'translation');
    assert.ok(translations.length > 0, JSON.stringify({ audioStatus, events }));
    assert.equal(events.filter(event => ['error', 'dropped'].includes(event.type)).length, 0, JSON.stringify(events));
    assert.ok(translations.every(event => event.zh && event.en));
    const chinese = translations.map(event => event.zh).join('');
    const english = translations.map(event => event.en).join(' ').toLowerCase();
    assert.match(chinese, /会议/, '中文必须译出真实语音中的会议，而不只是返回非空字段');
    assert.match(chinese, /电脑|计算机/, '中文必须保留携带电脑的要求');
    assert.match(english, /meeting/);
    assert.match(english, /computer|laptop/);
    assert.doesNotMatch(chinese, /上午|下午/);
    assert.doesNotMatch(english.replaceAll('.', ''), /\b(?:am|pm)\b/);
    assert.ok(await page.locator('.zh').last().textContent());
    await page.screenshot({ path: `.local/capture-${language}.png` });
    results.push({ language, events });
    console.log(`${language}: 真实标签页采集产生 ${translations.length} 条中英双语字幕`);
  }
  await mkdir('.local/benchmark', { recursive: true });
  await writeFile('.local/benchmark/browser-capture.json', JSON.stringify(results, null, 2));
} finally {
  await context.close();
  await new Promise(resolve => server.close(resolve));
}
