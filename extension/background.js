let creating;
let starting = false;

let preferenceQueue = Promise.resolve();
function preferencesTask(operation) {
  const result = preferenceQueue.then(operation);
  preferenceQueue = result.catch(() => {});
  return result;
}

async function migratePreferences(token) {
  const stored = await chrome.storage.local.get({ language: null, display: null, translate: null, partials: null, fontSize: null, preferencesMigratedToken: null });
  if (stored.preferencesMigratedToken === token) return;
  const patch = Object.fromEntries(['language', 'display', 'translate', 'partials', 'fontSize'].filter(key => stored[key] !== null).map(key => [key, stored[key]]));
  const response = await fetch('http://127.0.0.1:18765/preferences/initialize', {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(patch), signal: AbortSignal.timeout(2000),
  });
  if (response.status === 404) return; // Older servers cannot initialize shared preferences.
  if (!response.ok) throw new Error('无法迁移原有字幕设置，请检查服务和配对码后重试');
  await chrome.storage.local.set({ preferencesMigratedToken: token });
}

async function flushPreferences(token) {
  const { pendingPreferences } = await chrome.storage.local.get('pendingPreferences');
  if (!pendingPreferences || pendingPreferences.token !== token) return;
  const response = await fetch('http://127.0.0.1:18765/preferences', {
    method: 'PATCH', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(pendingPreferences.patch), signal: AbortSignal.timeout(2000),
  });
  if (!response.ok && response.status !== 404) throw new Error('设置尚未同步，请检查服务和配对码后重试');
  await chrome.storage.local.remove('pendingPreferences');
}

async function savePreferences(token, patch) {
  return preferencesTask(async () => {
    const { pendingPreferences } = await chrome.storage.local.get('pendingPreferences');
    const previous = pendingPreferences?.token === token ? pendingPreferences.patch : {};
    await chrome.storage.local.set({ ...patch, pendingPreferences: { token, patch: { ...previous, ...patch } } });
    try { await migratePreferences(token); await flushPreferences(token); return { ok: true }; }
    catch { return { error: '设置已保存在浏览器，将在下次开始字幕前重试同步。' }; }
  });
}

async function ensureOffscreen() {
  if ((await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] })).length) return;
  creating ??= chrome.offscreen.createDocument({
    url: 'offscreen.html', reasons: ['USER_MEDIA', 'AUDIO_PLAYBACK'],
    justification: '采集用户选定标签页音频，在本机生成双语字幕，同时保持原声播放。',
  }).finally(() => { creating = null; });
  await creating;
}

async function offscreen(type, payload = {}) {
  return chrome.runtime.sendMessage({ target: 'offscreen', type, ...payload });
}

async function forward(tabId, event) {
  try {
    await chrome.tabs.sendMessage(tabId, { target: 'overlay', event });
  } catch { /* Navigation may already have destroyed the overlay. */ }
}

async function handle(message) {
  if (message.type === 'migratePreferences') return preferencesTask(() => migratePreferences(message.token));
  if (message.type === 'savePreferences') return savePreferences(message.token, message.patch);
  if (message.type === 'status') {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
    return contexts.length ? offscreen('status') : { state: 'idle' };
  }
  if (message.type === 'stop') {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
    if (contexts.length) await offscreen('stop');
    return { ok: true };
  }
  if (message.type === 'start') {
    if (starting) throw new Error('正在启动，请稍候');
    starting = true;
    let resetSent = false;
    try {
      await ensureOffscreen();
      const current = await offscreen('status');
      if (current.state !== 'idle' && current.state !== 'error') {
        throw new Error('请先停止当前字幕，再开启另一个标签页');
      }
      const settings = await chrome.storage.local.get({ token: '', language: 'en', display: 'zh-en', translate: true, partials: true, fontSize: 26 });
      if (!settings.token.trim()) throw new Error('请先填写本地服务配对码');
      // Retry durable local edits before allowing a server GET to replace them.
      await preferencesTask(async () => {
        await migratePreferences(settings.token.trim());
        await flushPreferences(settings.token.trim());
        const response = await fetch('http://127.0.0.1:18765/preferences', {
          headers: { Authorization: `Bearer ${settings.token.trim()}` },
          signal: AbortSignal.timeout(2000),
        });
        if (response.ok) {
          const shared = await response.json();
          for (const key of ['language', 'display', 'translate', 'partials', 'fontSize']) if (Object.hasOwn(shared, key)) settings[key] = shared[key];
          await chrome.storage.local.set(settings);
        } else if (response.status !== 404) {
          throw new Error('无法同步字幕设置，请检查本机配对码');
        }
      });
      await chrome.scripting.executeScript({ target: { tabId: message.tabId }, files: ['overlay.js'] });
      // activeTab also covers same-origin embedded players (for example Bilibili).
      // Keep the main-frame overlay when a foreign frame cannot be injected.
      await chrome.scripting.executeScript({ target: { tabId: message.tabId, allFrames: true }, files: ['overlay.js'] }).catch(() => {});
      await forward(message.tabId, { type: 'reset', fontSize: settings.fontSize });
      resetSent = true;
      const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: message.tabId });
      const result = await offscreen('start', { streamId, tabId: message.tabId, settings });
      if (result?.error) throw new Error(result.error);
      return { ok: true };
    } catch (error) {
      if (resetSent) await forward(message.tabId, { type: 'state', state: 'error', message: error.message });
      throw error;
    } finally { starting = false; }
  }
  if (message.type === 'event') {
    if (message.event.type === 'state') {
      const active = ['starting', 'running', 'stopping'].includes(message.event.state);
      await chrome.action.setBadgeText({ text: active ? 'ON' : '' });
      await chrome.action.setBadgeBackgroundColor({ color: '#17675a' });
    }
    await forward(message.tabId, message.event);
    return { ok: true };
  }
  return { error: '未知操作' };
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.target !== 'background' || sender.id !== chrome.runtime.id) return;
  // A content script may stop its own capture, but may not select another tab.
  const fromContent = sender.tab && !sender.url?.startsWith(chrome.runtime.getURL(''));
  if (fromContent && message.type !== 'stop') return;
  if (fromContent) {
    handle({ type: 'status' }).then(async status => {
      if (status.tabId === sender.tab.id) await handle({ type: 'stop' });
      reply({ ok: true });
    }).catch(error => reply({ error: error.message }));
  } else {
    handle(message).then(reply).catch(error => reply({ error: error.message }));
  }
  return true;
});

async function stopForTab(tabId) {
  const status = await handle({ type: 'status' });
  if (status.tabId === tabId) await handle({ type: 'stop' });
}
chrome.tabs.onRemoved.addListener(tabId => { stopForTab(tabId).catch(() => {}); });
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === 'loading' || change.url) stopForTab(tabId).catch(() => {});
});
