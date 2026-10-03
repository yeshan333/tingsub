import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

function background({ busy = false, failure = 'capture', preferencesStatus = 200 } = {}) {
  const events = [];
  const startedSettings = [];
  const savedSettings = [];
  let denied = true;
  const chrome = {
    runtime: {
      getContexts: async () => [{}],
      onMessage: { addListener() {} },
      sendMessage: async message => {
        if (message.type === 'status') return { state: busy ? 'running' : 'idle' };
        if (message.type === 'start') startedSettings.push(message.settings);
        return failure === 'offscreen' ? { error: '连接失败' } : { ok: true };
      },
    },
    storage: { local: { get: async () => ({ token: 'paired', fontSize: 26 }), set: async value => savedSettings.push(value) } },
    scripting: { executeScript: async () => {} },
    tabCapture: { getMediaStreamId: async () => {
      if (denied && failure === 'capture') { denied = false; throw new Error('采集被拒绝'); }
      return 'stream';
    } },
    tabs: {
      sendMessage: async (id, message) => events.push({ id, ...message.event }),
      onRemoved: { addListener() {} }, onUpdated: { addListener() {} },
    },
  };
  const context = vm.createContext({ chrome, AbortSignal, fetch: async () => ({ ok: preferencesStatus === 200, status: preferencesStatus, json: async () => ({ language: 'ja', display: 'zh-en', partials: true, fontSize: 30 }) }) });
  vm.runInContext(readFileSync('extension/background.js', 'utf8'), context);
  return { events, startedSettings, savedSettings, start: () => vm.runInContext("handle({type:'start',tabId:7})", context) };
}

test('注入成功但采集被拒绝时浮层收到错误，下一次启动仍可成功', async () => {
  const { events, start } = background();
  await assert.rejects(start(), /采集被拒绝/);
  assert.deepEqual(events.map(e => e.type), ['reset', 'state']);
  assert.equal(events[1].state, 'error');
  assert.equal(events[1].message, '采集被拒绝');
  assert.equal(events[1].id, 7);
  assert.equal((await start()).ok, true);
});

test('本机连接启动失败时浮层和调用方收到相同错误', async () => {
  const { events, start } = background({ failure: 'offscreen' });
  await assert.rejects(start(), /连接失败/);
  assert.equal(events.at(-1).state, 'error');
  assert.equal(events.at(-1).message, '连接失败');
});

test('已有直播采集时拒绝新启动，不能重置或报错覆盖现有浮层', async () => {
  const { events, start } = background({ busy: true });
  await assert.rejects(start(), /请先停止/);
  assert.equal(events.length, 0);
});


test('开始采集时使用桌面共享的语言和字号，并同步浏览器设置', async () => {
  const { start, events, startedSettings, savedSettings } = background({ failure: 'none' });
  await start();
  assert.equal(startedSettings.length, 1);
  assert.equal(startedSettings[0].language, 'ja');
  assert.equal(startedSettings[0].fontSize, 30);
  assert.equal(events[0].fontSize, 30);
  assert.equal(savedSettings[0].language, 'ja');
});

test('共享设置认证失败时不注入字幕或启动音频采集', async () => {
  const { start, events, startedSettings } = background({ failure: 'none', preferencesStatus: 401 });
  await assert.rejects(start(), /配对码/);
  assert.equal(events.length, 0);
  assert.equal(startedSettings.length, 0);
});

test('旧服务没有共享设置接口时保留浏览器字号继续启动', async () => {
  const { start, events } = background({ failure: 'none', preferencesStatus: 404 });
  await start();
  assert.equal(events[0].fontSize, 26);
});
