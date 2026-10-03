const $ = id => document.getElementById(id);
const keys = ['token', 'language', 'display', 'partials', 'fontSize'];
const settings = await chrome.storage.local.get({ token: '', language: 'en', display: 'zh-en', partials: true, fontSize: 26 });
for (const key of keys) {
  if (key === 'partials') $(key).checked = settings[key];
  else $(key).value = settings[key];
}
$('sizeLabel').textContent = settings.fontSize;
if (!settings.token) document.querySelector('details').open = true;
async function save() {
  await chrome.storage.local.set({
    token: $('token').value.trim(), language: $('language').value, display: $('display').value,
    partials: $('partials').checked, fontSize: Number($('fontSize').value),
  });
  $('sizeLabel').textContent = $('fontSize').value;
}
let saving = Promise.resolve();
async function loadShared() {
  const token = $('token').value.trim();
  if (!token) return;
  try {
    const response = await fetch('http://127.0.0.1:18765/preferences', {
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(1200),
    });
    if (!response.ok) return;
    const shared = await response.json();
    for (const key of keys.filter(key => key !== 'token')) {
      if (key === 'partials') $(key).checked = shared[key]; else $(key).value = shared[key];
    }
    await save();
  } catch { /* Offline editing remains available in browser storage. */ }
}
keys.forEach(key => $(key).addEventListener('input', () => {
  const value = key === 'partials' ? $(key).checked : key === 'fontSize' ? Number($(key).value) : $(key).value;
  const token = $('token').value.trim();
  save();
  if (key === 'token') return;
  saving = saving.then(async () => {
    if (!token) return;
    try {
      const response = await fetch('http://127.0.0.1:18765/preferences', {
        method: 'PATCH', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }), signal: AbortSignal.timeout(1200),
      });
      if (!response.ok && response.status !== 404) throw new Error();
    } catch { status('设置仅保存在浏览器；服务恢复后请重新设置以同步桌面端。', true); }
  });
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
