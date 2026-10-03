import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

test('关闭翻译连接旧服务时明确拒绝启动，不能悄悄继续翻译', async () => {
  const context = vm.createContext({
    chrome:{runtime:{onMessage:{addListener(){}},sendMessage:async()=>({})}},
    AbortSignal,
    fetch:async()=>({ok:true,json:async()=>({service:'tingqiao',protocol:1,ready:true})}),
    WebSocket:class { constructor(){throw new Error('Must not send audio to an incompatible session');} },
  });
  vm.runInContext(readFileSync('extension/offscreen.js','utf8'),context);
  await assert.rejects(vm.runInContext("new Session({settings:{translate:false}}).start()",context),/不支持关闭翻译/);
});
