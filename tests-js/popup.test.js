import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

async function popup({ migrationFails = false, session = { state: 'idle' }, startResult = { ok: true } } = {}) {
  let interval;
  const elements = {};
  const requests = [];
  const saved = [];
  const defaults = { token: 'first-pairing', language: 'en', display: 'zh-en', partials: true, fontSize: 26 };
  function element(id) {
    return elements[id] ??= {
      value: '', checked: false, listeners: {}, classList: { toggle() {} },
      addEventListener(type, handler) { this.listeners[type] = handler; },
    };
  }
  const chrome = {
    tabs: { query: async () => [{ id: 12, url: 'https://www.youtube.com/watch?v=test' }] },
    storage: { local: { get: async () => defaults, set: async value => saved.push({ ...value }) } },
    runtime: { sendMessage: async message => {
      if (message.type === 'migratePreferences' && migrationFails) return { error: 'migration unavailable' };
      if (message.type === 'start') return startResult;
      return session;
    } },
  };
  const context = vm.createContext({
    chrome, AbortSignal,
    document: { getElementById: element, querySelector: () => ({ open: false }) },
    setInterval(callback) { interval = callback; },
    fetch: async (url, options) => {
      if (url.endsWith('/health')) return { ok: true, json: async () => ({ service: 'tingqiao', protocol: 1 }) };
      if (options.method === 'PATCH') return { ok: true };
      return new Promise(resolve => requests.push({ token: options.headers.Authorization, resolve: value => resolve({ ok: true, json: async () => value }) }));
    },
  });
  const loaded = vm.runInContext(`(async () => { ${readFileSync('extension/popup.js', 'utf8')} })()`, context);
  let finished = false;
  loaded.finally(() => { finished = true; });
  while (!requests.length && !finished) await new Promise(resolve => setImmediate(resolve));
  return { elements, requests, saved, loaded, refresh: () => interval(), edit: async (id, value) => {
    elements[id].value = value;
    await elements[id].listeners.input();
  } };
}

test('初次读取共享设置尚未返回时，用户编辑的语言不被旧响应覆盖，其他字段仍加载', async () => {
  const ui = await popup();
  await ui.edit('language', 'ja');
  ui.requests[0].resolve({ language: 'en', display: 'source-zh', partials: false, fontSize: 30 });
  await ui.loaded;
  assert.equal(ui.elements.language.value, 'ja');
  assert.equal(ui.saved.at(-1).language, 'ja');
  assert.equal(ui.elements.display.value, 'source-zh');
  assert.equal(ui.elements.fontSize.value, 30);
});

test('用户切换配对码后，上一配对请求的旧响应不能覆盖新配对设置', async () => {
  const ui = await popup();
  await ui.edit('token', 'second-pairing');
  const changed = ui.elements.token.listeners.change();
  while (ui.requests.length < 2) await new Promise(resolve => setImmediate(resolve));
  assert.equal(ui.requests.length, 2);
  ui.requests[1].resolve({ language: 'ja', display: 'source-zh', partials: false, fontSize: 32 });
  await changed;
  ui.requests[0].resolve({ language: 'en', display: 'zh-en', partials: true, fontSize: 26 });
  await ui.loaded;
  assert.equal(ui.elements.language.value, 'ja');
  assert.equal(ui.elements.fontSize.value, 32);
  assert.equal(ui.saved.at(-1).token, 'second-pairing');
  assert.equal(ui.saved.at(-1).language, 'ja');
});


test('旧设置迁移失败时弹窗保留本地值且不读取服务默认值', async () => {
  const ui = await popup({ migrationFails: true });
  await ui.loaded;
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.elements.language.value, 'en');
  assert.equal(ui.elements.fontSize.value, 26);
  assert.equal(ui.saved.length, 0);
});


test('字幕启动被拒绝后，定时刷新仍显示失败原因而不是模型就绪', async () => {
  const ui = await popup({ startResult: { error: '无法采集当前标签页音频' } });
  ui.requests[0].resolve({});
  await ui.loaded;
  await ui.elements.start.listeners.click();
  await ui.refresh();
  await ui.refresh();
  assert.equal(ui.elements.status.textContent, '无法采集当前标签页音频');
  assert.equal(ui.elements.start.disabled, false);
});

test('字幕启动失败后重试成功，弹窗恢复正在聆听状态', async () => {
  const session = { state: 'idle' };
  const startResult = { error: '无法采集当前标签页音频' };
  const ui = await popup({ session, startResult });
  ui.requests[0].resolve({});
  await ui.loaded;
  await ui.elements.start.listeners.click();
  delete startResult.error;
  startResult.ok = true;
  session.state = 'running';
  session.audio = { rms: 200 };
  await ui.elements.start.listeners.click();
  await ui.refresh();
  assert.match(ui.elements.status.textContent, /正在聆听.*已收到直播声音/);
  assert.equal(ui.elements.start.disabled, true);
  assert.equal(ui.elements.stop.disabled, false);
});

test('已有字幕会话停止后，重新打开弹窗明确提示需要再次开启字幕', async () => {
  const ui = await popup({ session: { state: 'idle', tabId: 12, message: '字幕已停止' } });
  ui.requests[0].resolve({});
  await ui.loaded;
  await ui.refresh();
  assert.match(ui.elements.status.textContent, /字幕已停止.*重新开始/);
  assert.equal(ui.elements.start.disabled, false);
  assert.equal(ui.elements.stop.disabled, true);
});
