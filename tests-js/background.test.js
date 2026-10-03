import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

function background({ busy = false, failure = 'capture', preferencesStatus = 200, sharedStorage, initialized = true, frameDenied = false } = {}) {
  const events = [];
  const injections = [];
  const startedSettings = [];
  const savedSettings = [];
  let denied = true;
  let online = true;
  const storage = sharedStorage || { token: 'paired', fontSize: 26 };
  const serverPreferences = { language: 'ja', display: 'zh-en', partials: true, fontSize: 30 };
  const requests = [];
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
    storage: { local: {
      get: async keys => typeof keys === 'string' ? { [keys]: storage[keys] } : Object.fromEntries(Object.entries(keys).map(([key, fallback]) => [key, Object.hasOwn(storage, key) ? storage[key] : fallback])),
      set: async value => { savedSettings.push(value); Object.assign(storage, structuredClone(value)); },
      remove: async key => { delete storage[key]; },
    } },
    scripting: { executeScript: async options => { injections.push(options.target); if(options.target.allFrames && frameDenied) throw new Error('Cannot access foreign frame'); } },
    tabCapture: { getMediaStreamId: async () => {
      if (denied && failure === 'capture') { denied = false; throw new Error('采集被拒绝'); }
      return 'stream';
    } },
    tabs: {
      sendMessage: async (id, message) => events.push({ id, ...message.event }),
      onRemoved: { addListener() {} }, onUpdated: { addListener() {} },
    },
  };
  const context = vm.createContext({ chrome, AbortSignal, fetch: async (url, options) => {
    if (!online) throw new Error('offline');
    requests.push(options.method || 'GET');
    if (options.method === 'POST' && preferencesStatus === 200 && !initialized) { Object.assign(serverPreferences, JSON.parse(options.body)); initialized = true; }
    if (options.method === 'PATCH' && preferencesStatus === 200) Object.assign(serverPreferences, JSON.parse(options.body));
    return { ok: preferencesStatus === 200, status: preferencesStatus, json: async () => ({ ...serverPreferences }) };
  } });
  vm.runInContext(readFileSync('extension/background.js', 'utf8'), context);
  return { injections, events, startedSettings, savedSettings, storage, requests,
    setOnline(value) { online = value; },
    save: patch => { context.patch = patch; return vm.runInContext("handle({type:'savePreferences',token:'paired',patch})", context); },
    start: () => vm.runInContext("handle({type:'start',tabId:7})", context) };
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
  assert.equal(savedSettings.at(-1).language, 'ja');
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


test('离线编辑跨后台重启保留，恢复连接后先重试写入再读取并开始采集', async () => {
  const first = background({ failure: 'none' });
  first.setOnline(false);
  assert.match((await first.save({ language: 'en' })).error, /重试/);
  await first.save({ fontSize: 34 });
  assert.deepEqual(first.storage.pendingPreferences.patch, { language: 'en', fontSize: 34 });
  const restarted = background({ failure: 'none', sharedStorage: first.storage });
  await restarted.start();
  assert.deepEqual(restarted.requests, ['POST', 'PATCH', 'GET']);
  assert.equal(restarted.startedSettings[0].language, 'en');
  assert.equal(restarted.startedSettings[0].fontSize, 34);
  assert.equal(restarted.storage.pendingPreferences, undefined);
});

test('待同步设置再次提交失败时不采集音频也不丢弃用户编辑', async () => {
  const ui = background({ failure: 'none' });
  ui.setOnline(false);
  await ui.save({ fontSize: 36 });
  await assert.rejects(ui.start(), /offline/);
  assert.equal(ui.startedSettings.length, 0);
  assert.equal(ui.events.length, 0);
  assert.equal(ui.storage.pendingPreferences.patch.fontSize, 36);
});


test('旧插件首次连接没有共享配置的服务时先迁移所有原设置再开始字幕', async () => {
  const storage = { token: 'paired', language: 'auto', display: 'source-zh', partials: false, fontSize: 38 };
  const expected = { ...storage };
  const ui = background({ failure: 'none', sharedStorage: storage, initialized: false });
  await ui.start();
  assert.deepEqual(ui.requests, ['POST', 'GET']);
  for (const key of ['language', 'display', 'partials', 'fontSize']) {
    assert.equal(ui.startedSettings[0][key], expected[key]);
  }
  assert.equal(storage.preferencesMigratedToken, 'paired');
  await ui.start();
  assert.deepEqual(ui.requests, ['POST', 'GET', 'GET']);
});

test('旧插件的首次迁移不能覆盖桌面已经保存的共享设置', async () => {
  const ui = background({ failure: 'none', sharedStorage: { token: 'paired', language: 'en', fontSize: 38 } });
  await ui.start();
  assert.equal(ui.startedSettings[0].language, 'ja');
  assert.equal(ui.startedSettings[0].fontSize, 30);
});


test('同源嵌入播放器随主页面接收字幕，外域框架权限不足也不阻断主页面采集', async () => {
  for (const frameDenied of [false,true]) {
    const {start,injections,events,startedSettings} = background({failure:'none',frameDenied});
    assert.equal((await start()).ok,true);
    assert.equal(injections.some(target=>target.tabId===7 && target.allFrames),true);
    assert.equal(events[0].type,'reset');
    assert.equal(startedSettings.length,1);
  }
});


test('用户关闭翻译后，新采集会话保持关闭并保留目标语言选择', async () => {
  const {save,start,startedSettings,storage} = background({failure:'none'});
  await save({translate:false});
  await start();
  assert.equal(startedSettings[0].translate,false);
  assert.equal(storage.translate,false);
  assert.equal(startedSettings[0].display,'zh-en');
});
