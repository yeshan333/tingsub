import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

function processor() {
  const packets = [];
  let Processor;
  const context = vm.createContext({
    AudioWorkletProcessor: class {
      constructor() { this.port = { postMessage: buffer => packets.push(buffer) }; }
    },
    registerProcessor: (_, implementation) => { Processor = implementation; },
    currentTime: 0, sampleRate: 16000,
  });
  vm.runInContext(readFileSync('extension/pcm-worklet.js', 'utf8'), context);
  const instance = new Processor();
  instance.port.onmessage({ data: { type: 'clock', epoch: 1000 } });
  return { instance, packets, context };
}

test('立体声经过跨音频块拼接后生成连续的20毫秒单声道帧', () => {
  const { instance, packets, context } = processor();
  for (let n = 0; n < 5; n++) {
    context.currentTime = n * 128 / 16000;
    instance.process([[new Float32Array(128).fill(0.8), new Float32Array(128).fill(0.2)]]);
  }
  assert.equal(packets.length, 2);
  assert.equal(packets[0].byteLength, 648);
  assert.equal(new DataView(packets[0]).getFloat64(0, true), 1020);
  assert.equal(new DataView(packets[1]).getFloat64(0, true), 1040);
  for (const packet of packets) {
    const view = new DataView(packet);
    for (let offset = 8; offset < 648; offset += 2) assert.equal(view.getInt16(offset, true), 16384);
  }
});

test('音量溢出时PCM采样饱和截断而不是整数回绕', () => {
  const { instance, packets } = processor();
  const samples = new Float32Array(320).fill(2);
  samples[1] = -2;
  instance.process([[samples]]);
  const view = new DataView(packets[0]);
  assert.equal(view.getInt16(8, true), 32767);
  assert.equal(view.getInt16(10, true), -32768);
});


test('输入通道临时消失时发送带连续时间戳的静音帧，恢复后保留新声音', () => {
  const { instance, packets, context } = processor();
  for (let n = 0; n < 5; n++) {
    context.currentTime = n * 128 / 16000;
    instance.process([[]]);
  }
  context.currentTime = 0.04;
  instance.process([[new Float32Array(320).fill(.5)]]);
  assert.equal(packets.length, 3);
  assert.deepEqual(packets.map(p => new DataView(p).getFloat64(0, true)), [1020, 1040, 1060]);
  for (const packet of packets.slice(0, 2)) {
    const view = new DataView(packet);
    for (let i = 8; i < 648; i += 2) assert.equal(view.getInt16(i, true), 0);
  }
  const restored = new DataView(packets[2]);
  for (let i = 8; i < 648; i += 2) assert.equal(restored.getInt16(i, true), 16384);
});
