const $ = id => document.getElementById(id);
const keys = ['token', 'language', 'display', 'translate', 'partials', 'fontSize'];
const settings = await chrome.storage.local.get({ token: '', language: 'en', display: 'zh-en', translate: true, partials: true, fontSize: 26 });
for (const key of keys) {
  if ((key === 'partials' || key === 'translate')) $(key).checked = settings[key];
  else $(key).value = settings[key];
}
$('sizeLabel').textContent = settings.fontSize;
$('display').disabled = !$('translate').checked;
if (!settings.token) document.querySelector('details').open = true;
async function save() {
  await chrome.storage.local.set({
    token: $('token').value.trim(), language: $('language').value, display: $('display').value,
    translate: $('translate').checked, partials: $('partials').checked, fontSize: Number($('fontSize').value),
  });
  $('sizeLabel').textContent = $('fontSize').value;
  $('display').disabled = !$('translate').checked;
}
let saving = Promise.resolve();
const editVersions = Object.fromEntries(keys.map(key => [key, 0]));
async function loadShared() {
  const token = $('token').value.trim();
  const versions = { ...editVersions };
  if (!token) return;
  try {
    const migration = await chrome.runtime.sendMessage({ target: 'background', type: 'migratePreferences', token });
    if (migration?.error) throw new Error(migration.error);
    const { pendingPreferences: pendingBefore } = await chrome.storage.local.get('pendingPreferences');
    const response = await fetch('http://127.0.0.1:18765/preferences', {
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(1200),
    });
    if (!response.ok) return;
    const shared = await response.json();
    const { pendingPreferences } = await chrome.storage.local.get('pendingPreferences');
    if (token !== $('token').value.trim() || versions.token !== editVersions.token) return;
    for (const key of keys.filter(key => key !== 'token')) {
      if (!Object.hasOwn(shared, key) || versions[key] !== editVersions[key]) continue;
      if ([pendingBefore, pendingPreferences].some(pending => pending?.token === token && Object.hasOwn(pending.patch, key))) continue;
      if ((key === 'partials' || key === 'translate')) $(key).checked = shared[key]; else $(key).value = shared[key];
    }
    await save();
  } catch { /* Offline editing remains available in browser storage. */ }
}
keys.forEach(key => $(key).addEventListener('input', () => {
  editVersions[key]++;
  const value = (key === 'partials' || key === 'translate') ? $(key).checked : key === 'fontSize' ? Number($(key).value) : $(key).value;
  const token = $('token').value.trim();
  save();
  if (key === 'token') return;
  if (!token) return;
  // Hand off immediately: closing the popup must not discard queued edits.
  const request = chrome.runtime.sendMessage({
    target: 'background', type: 'savePreferences', token, patch: { [key]: value },
  }).then(result => {
    if (result?.error) status(result.error, true);
  }).catch(() => status('设置同步失败，请重新打开插件后重试。', true));
  saving = Promise.all([saving, request]);
}));
$('token').addEventListener('change', loadShared);
let pending = false;
function status(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
async function refresh() {
  if (pending) return;
  const current = await chrome.runtime.sendMessage({ target: 'background', type: 'status' });
  const active = ['starting', 'running', 'stopping'].includes(current.state);
  $('start').disabled = active;
  $('stop').disabled = !active || current.state === 'stopping';
  if (active || current.state === 'error') {
    const message = current.state === 'running' && current.audio
      ? `正在聆听 · ${current.audio.rms > 100 ? '已收到直播声音' : '等待直播声音'}`
      : current.message || '正在聆听…';
    status(message, current.state === 'error');
    return;
  }
  try {
    const response = await fetch('http://127.0.0.1:18765/health', { signal: AbortSignal.timeout(1200) });
    if (!response.ok) throw new Error();
    const health = await response.json();
    if (health.service !== 'tingqiao' || health.protocol !== 1) {
      status('端口被其他服务占用，无法连接听桥', true); return;
    }
    status(health.busy ? '本机模型正在处理另一个连接' : '本机模型已就绪，打开直播后即可开始');
  } catch { status('本机服务未就绪。请在 TingSub 桌面窗口启动服务，或运行 start.command。', true); }
}
$('start').addEventListener('click', async () => {
  pending = true;
  $('start').disabled = true;
  try {
    await save();
    await saving;
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https?:/.test(tab.url || '')) throw new Error('请在 YouTube 等视频网页中开启字幕');
    status('正在连接直播音频…');
    const result = await chrome.runtime.sendMessage({ target: 'background', type: 'start', tabId: tab.id });
    if (result?.error) throw new Error(result.error);
    pending = false;
    await refresh();
  } catch (error) { status(error.message, true); $('start').disabled = false; }
  finally { pending = false; }
});
$('stop').addEventListener('click', async () => {
  $('stop').disabled = true;
  await chrome.runtime.sendMessage({ target: 'background', type: 'stop' });
  await refresh();
});
await loadShared();
await refresh();
setInterval(() => { refresh().catch(error => status(error.message, true)); }, 2000);
