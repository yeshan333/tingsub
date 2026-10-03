import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

async function popup() {
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
    storage: { local: { get: async () => defaults, set: async value => saved.push({ ...value }) } },
    runtime: { sendMessage: async () => ({ state: 'idle' }) },
  };
  const context = vm.createContext({
    chrome, AbortSignal,
    document: { getElementById: element, querySelector: () => ({ open: false }) },
    setInterval() {},
    fetch: async (url, options) => {
      if (url.endsWith('/health')) return { ok: true, json: async () => ({ service: 'tingqiao', protocol: 1 }) };
      if (options.method === 'PATCH') return { ok: true };
      return new Promise(resolve => requests.push({ token: options.headers.Authorization, resolve: value => resolve({ ok: true, json: async () => value }) }));
    },
  });
  const loaded = vm.runInContext(`(async () => { ${readFileSync('extension/popup.js', 'utf8')} })()`, context);
  while (!requests.length) await new Promise(resolve => setImmediate(resolve));
  return { elements, requests, saved, loaded, edit: async (id, value) => {
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
