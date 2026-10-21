// Opt-in integration test: a real public YouTube livestream, no network or model mocks.
// Start TingSub with cached models, then set TINGSUB_DATA_DIR and YOUTUBE_LIVE_URL.
import { chromium } from 'playwright';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import assert from 'node:assert/strict';

const scenario = 'YouTube 直播播放时，开启 TingSub 后持续显示本机识别与翻译的双语字幕';
const directory = resolve(process.env.TINGSUB_DATA_DIR || '.local');
const output = resolve(process.env.YOUTUBE_TEST_OUTPUT || '.local/youtube-live');
const url = process.env.YOUTUBE_LIVE_URL || 'https://www.youtube.com/@dwnews/live';
const duration = Number(process.env.YOUTUBE_TEST_SECONDS || 180);
assert.ok(Number.isFinite(duration) && duration >= 30 && duration <= 3600);
assert.ok(new URL(url).hostname === 'www.youtube.com', 'Use a public YouTube livestream URL');
await mkdir(output, { recursive: true });
const token = (await readFile(join(directory, 'token'), 'utf8')).trim();
const report = { scenario, started_at: new Date().toISOString(), requested_url: url, duration_seconds: duration, samples: [] };
const preferencesResponse = await fetch('http://127.0.0.1:18765/preferences', { headers: { Authorization: `Bearer ${token}` } });
assert.equal(preferencesResponse.ok, true, 'Read shared preferences before changing test settings');
const originalPreferences = await preferencesResponse.json();
const context = await chromium.launchPersistentContext('', {
  channel: 'chromium', headless: process.env.HEADED !== '1',
  ...(process.env.YOUTUBE_TEST_PROXY ? { proxy: { server: process.env.YOUTUBE_TEST_PROXY, bypass: '127.0.0.1,localhost' } } : {}),
  ignoreDefaultArgs: ['--mute-audio'],
  args: ['--enable-unsafe-extension-debugging', '--autoplay-policy=no-user-gesture-required',
    `--disable-extensions-except=${resolve('extension')}`, `--load-extension=${resolve('extension')}`],
});
let page, worker, control, capturing = false;
const playerState = () => {
  const player = document.getElementById('movie_player');
  const video = document.querySelector('video');
  const response = player?.getPlayerResponse?.() || window.ytInitialPlayerResponse;
  return {
    title: response?.videoDetails?.title, video_id: response?.videoDetails?.videoId,
    live: response?.microformat?.playerMicroformatRenderer?.liveBroadcastDetails,
    is_live_content: response?.videoDetails?.isLiveContent,
    playability: response?.playabilityStatus?.status,
    player_error: document.querySelector('.ytp-error')?.textContent,
    paused: video?.paused, muted: video?.muted, volume: video?.volume,
    time: video?.currentTime, ready_state: video?.readyState,
    ad: player?.classList.contains('ad-showing'),
  };
};
try {
  const health = await (await fetch('http://127.0.0.1:18765/health')).json();
  assert.equal(health.ready, true, 'TingSub must finish warming its local models');
  assert.equal(health.busy, false, 'Do not interrupt another capture session');
  report.browser = context.browser().version();
  worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const id = new URL(worker.url()).host;
  await worker.evaluate(async settings => {
    await chrome.storage.local.set(settings);
    globalThis.captureEvents = [];
    chrome.runtime.onMessage.addListener(message => {
      if (message.type === 'event') captureEvents.push({ ...message.event,
        received_ms: Date.now(),
        end_to_end_ms: message.event.speech_end_ms ? Math.round(Date.now() - message.event.speech_end_ms) : undefined,
      });
    });
  }, { token, language: 'en', display: 'zh-en', translate: true, partials: true, fontSize: 26 });
  page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const rejectCookies = page.getByRole('button', { name: /Reject all|拒绝全部/ }).first();
  if (await rejectCookies.isVisible()) await rejectCookies.click();
  await page.waitForFunction(() => document.querySelector('video') && document.getElementById('movie_player')?.getPlayerResponse?.()?.playabilityStatus, null, { timeout: 45000 });
  const initialPlayer = await page.evaluate(playerState);
  assert.equal(initialPlayer.playability, 'OK', `YouTube cannot play: ${JSON.stringify(initialPlayer)}`);
  await page.evaluate(async () => {
    const video = document.querySelector('video');
    const player = document.getElementById('movie_player');
    player.unMute(); player.setVolume(100); player.playVideo();
    video.muted = false; await video.play();
  });
  await page.waitForFunction(() => {
    const v = document.querySelector('video');
    return v && !v.paused && !v.muted && v.readyState >= 3 && !document.getElementById('movie_player').classList.contains('ad-showing');
  }, null, { timeout: 60000 });
  report.player_start = await page.evaluate(playerState);
  report.resolved_url = page.url();
  assert.equal(report.player_start.is_live_content, true, 'The source must be a livestream');
  assert.equal(report.player_start.live?.isLiveNow, true, 'The broadcast must currently be live, not a replay');
  console.log(JSON.stringify({ scenario, player: report.player_start, url: page.url() }));
  const cdp = await context.browser().newBrowserCDPSession();
  const { targetInfos } = await cdp.send('Target.getTargets', { filter: [{ type: 'tab' }] });
  const target = targetInfos.find(target => target.url === page.url());
  assert.ok(target, 'YouTube tab must be available for real tab capture');
  await page.bringToFront();
  await cdp.send('Extensions.triggerAction', { id, targetId: target.targetId });
  control = await context.newPage();
  await control.goto(`chrome-extension://${id}/popup.html`);
  const saved = await control.evaluate(token => chrome.runtime.sendMessage({
    target: 'background', type: 'savePreferences', token,
    patch: { language: 'en', display: 'zh-en', translate: true, partials: true, fontSize: 26 },
  }), token);
  assert.equal(saved.ok, true, JSON.stringify(saved));
  const tabs = await worker.evaluate(() => chrome.tabs.query({}));
  const videoTab = tabs.find(tab => tab.url === page.url());
  assert.ok(videoTab);
  const start = await control.evaluate(tabId => chrome.runtime.sendMessage({ target: 'background', type: 'start', tabId }), videoTab.id);
  assert.equal(start.ok, true, JSON.stringify(start));
  capturing = true;
  await page.bringToFront();
  await page.waitForFunction(() => document.getElementById('tingqiao-local-captions')?.shadowRoot.querySelector('.state').textContent.includes('正在聆听'));
  const started = Date.now();
  while (Date.now() - started < duration * 1000) {
    await new Promise(resolve => setTimeout(resolve, Math.min(10000, duration * 1000 - (Date.now() - started))));
    const events = await worker.evaluate(() => captureEvents);
    const audio = await worker.evaluate(() => chrome.runtime.sendMessage({ target: 'offscreen', type: 'status' }));
    const player = await page.evaluate(playerState);
    const sample = { elapsed_seconds: Math.round((Date.now() - started) / 1000), audio, player,
      translations: events.filter(e => e.type === 'translation').length };
    report.samples.push(sample);
    console.log(JSON.stringify(sample));
    assert.equal(audio.state, 'running', 'Capture must remain running throughout the live broadcast');
    if (sample.translations) await page.screenshot({ path: join(output, 'youtube-captions.png') });
  }
  report.player_end = await page.evaluate(playerState);
  assert.ok(report.player_end.time - report.player_start.time >= duration * 0.7, 'The live player must advance during capture');
  // Read the actual rendered shadow DOM instead of relying only on server events.
  report.overlay = await page.locator('#tingqiao-local-captions .zh, #tingqiao-local-captions .en').allTextContents();
  assert.ok((await page.locator('#tingqiao-local-captions .zh').allTextContents()).some(text => /[\u4e00-\u9fff]/.test(text)), 'Chinese subtitles must be rendered');
  await control.evaluate(() => chrome.runtime.sendMessage({ target: 'background', type: 'stop' }));
  const deadline = Date.now() + 45000;
  let status;
  do {
    status = await worker.evaluate(() => chrome.runtime.sendMessage({ target: 'offscreen', type: 'status' }));
    if (['idle', 'error'].includes(status.state)) break;
    await new Promise(resolve => setTimeout(resolve, 200));
  } while (Date.now() < deadline);
  capturing = false;
  report.stop_status = status;
  assert.equal(status.state, 'idle', 'Stopping should drain the final utterance and release capture');
  report.events = await worker.evaluate(() => captureEvents);
  const translations = report.events.filter(event => event.type === 'translation');
  report.counts = Object.fromEntries([...new Set(report.events.map(e => e.type))].map(type => [type, report.events.filter(e => e.type === type).length]));
  const latencies = translations.map(e => e.end_to_end_ms).filter(Number.isFinite).sort((a, b) => a - b);
  report.latency_ms = { count: latencies.length, p50: latencies[Math.ceil(latencies.length * .5) - 1], p95: latencies[Math.ceil(latencies.length * .95) - 1] };
  assert.ok(translations.length >= 3, 'At least three complete bilingual captions should arrive from actual live speech');
  assert.ok(translations.every(e => e.zh && e.en), 'Every translated caption must contain both languages');
  assert.equal(report.events.filter(e => ['error', 'dropped'].includes(e.type)).length, 0, 'No audio or utterance should be dropped');
  report.result = 'passed';
  console.log(JSON.stringify({ result: report.result, counts: report.counts, latency_ms: report.latency_ms }));
} catch (error) {
  report.result = 'failed';
  report.error = error.stack;
  if (page) {
    report.failed_url = page.url();
    report.failed_player = await page.evaluate(playerState).catch(() => null);
    report.page_text = (await page.locator('body').innerText().catch(() => '')).slice(0, 12000);
    await page.screenshot({ path: join(output, 'failure.png') }).catch(() => {});
  }
  if (worker) report.events = await worker.evaluate(() => captureEvents).catch(() => []);
  throw error;
} finally {
  if (capturing && control) await control.evaluate(() => chrome.runtime.sendMessage({ target: 'background', type: 'stop' })).catch(() => {});
  report.finished_at = new Date().toISOString();
  await writeFile(join(output, 'report.json'), JSON.stringify(report, null, 2));
  await context.close();
  const restored = await fetch('http://127.0.0.1:18765/preferences', {
    method: 'PATCH', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(originalPreferences),
  });
  assert.equal(restored.ok, true, 'Restore shared preferences after testing');

}
