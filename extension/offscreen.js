let session;
let lastStatus = { state: 'idle' };

class Session {
  constructor({ tabId, settings, streamId }) {
    Object.assign(this, { tabId, settings, streamId });
    this.state = 'starting';
    this.closed = false;
    this.audio = { frames: 0, rms: 0 };
  }
  async emit(event) {
    if (event.type === 'state') {
      this.state = event.state;
      lastStatus = { state: event.state, tabId: this.tabId, message: event.message || '' };
    }
    try { await chrome.runtime.sendMessage({ target: 'background', type: 'event', tabId: this.tabId, event }); }
    catch { /* Extension may have been reloaded. */ }
  }
  assertActive() { if (this.closed) throw new Error('已取消启动'); }

  async start() {
    await this.emit({ type: 'state', state: 'starting', message: '连接本地模型…' });
    const response = await fetch('http://127.0.0.1:18765/health', { signal: AbortSignal.timeout(3000) })
      .catch(() => { throw new Error('无法连接本机字幕服务，请运行 start.command 并等待模型预热完成'); });
    if (!response.ok) throw new Error('本机字幕服务未就绪');
    const health = await response.json();
    if (health.service !== 'tingqiao' || health.protocol !== 1 || !health.ready) {
      throw new Error('端口上的服务不是兼容的听桥字幕服务');
    }
    this.assertActive();
    this.ws = new WebSocket('ws://127.0.0.1:18765/stream');
    this.ws.binaryType = 'arraybuffer';
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('本地服务未就绪，请先启动并等待模型预热完成')), 8000);
      const settle = (error) => { clearTimeout(timeout); error ? reject(error) : resolve(); };
      this.ws.onopen = () => this.ws.send(JSON.stringify({
        token: this.settings.token, language: this.settings.language,
        display: this.settings.display, partials: this.settings.partials,
      }));
      this.ws.onerror = () => settle(new Error('无法连接本地服务，请先运行 start.command'));
      this.ws.onclose = event => {
        const error = new Error(event.reason || '本地服务已断开，请重新开始');
        settle(error);
        if (!this.closed) void this.fail(error);
      };
      this.ws.onmessage = ({ data }) => {
        let event;
        try { event = JSON.parse(data); } catch { void this.fail(new Error('字幕服务返回了无效消息')); return; }
        if (event.type === 'ready') settle();
        else if (event.type === 'done') void this.cleanup('idle');
        else if (event.type !== 'pong') void this.emit(event);
      };
    });
    this.assertActive();
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: this.streamId } },
      video: false,
    });
    if (this.closed) { this.stream.getTracks().forEach(track => track.stop()); this.assertActive(); }
    for (const track of this.stream.getTracks()) track.onended = () => { void this.stop(); };
    // Monitor at the native rate so the user's original audio is not reduced to 16 kHz.
    this.monitor = new AudioContext();
    this.monitor.createMediaStreamSource(this.stream).connect(this.monitor.destination);
    this.context = new AudioContext({ sampleRate: 16000, latencyHint: 'interactive' });
    await this.context.audioWorklet.addModule('pcm-worklet.js');
    this.assertActive();
    if (this.context.sampleRate !== 16000) throw new Error('浏览器无法提供 16 kHz 音频上下文');
    this.node = new AudioWorkletNode(this.context, 'pcm16');
    const mute = this.context.createGain();
    mute.gain.value = 0;
    this.context.createMediaStreamSource(this.stream).connect(this.node);
    this.node.connect(mute).connect(this.context.destination);
    this.node.port.onmessage = ({ data }) => {
      if (this.closed || this.state !== 'running') return;
      this.audio.frames++;
      if (this.audio.frames % 10 === 0) {
        const view = new DataView(data);
        let energy = 0;
        for (let offset = 8; offset < data.byteLength; offset += 2) {
          const sample = view.getInt16(offset, true); energy += sample * sample;
        }
        this.audio.rms = Math.round(Math.sqrt(energy / 320));
      }
      if (this.ws.readyState !== WebSocket.OPEN || this.ws.bufferedAmount > 648 * 50) {
        // Never silently discard audio and stitch two different moments together.
        void this.fail(new Error('本地音频连接阻塞超过一秒，已停止；请重新开始'));
        return;
      }
      this.ws.send(data);
    };
    await Promise.all([this.monitor.resume(), this.context.resume()]);
    this.assertActive();
    this.node.port.postMessage({ type: 'clock', epoch: Date.now() - this.context.currentTime * 1000 });
    await this.emit({ type: 'state', state: 'running', message: '正在聆听 · 全部在本机处理' });
  }

  async releaseAudio() {
    if (this.node) { this.node.port.onmessage = null; this.node.disconnect(); }
    this.stream?.getTracks().forEach(track => { track.onended = null; track.stop(); });
    await Promise.allSettled([this.context?.close(), this.monitor?.close()]);
  }
  async stop() {
    if (this.closed || this.state === 'stopping') return;
    await this.emit({ type: 'state', state: 'stopping', message: '正在完成最后一句…' });
    await this.releaseAudio();
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'stop' }));
      this.stopTimer = setTimeout(() => { void this.fail(new Error('最后一句处理超时，已停止')); }, 32000);
    } else await this.cleanup('idle');
  }
  async fail(error) {
    await this.cleanup('error', error.message);
  }
  async cleanup(state, message = '') {
    if (this.closed) return;
    this.closed = true;
    clearTimeout(this.stopTimer);
    await this.releaseAudio();
    this.ws?.close();
    await this.emit({ type: 'state', state, message: message || '字幕已停止' });
    if (session === this) session = null;
  }
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.target !== 'offscreen' || sender.id !== chrome.runtime.id) return;
  (async () => {
    if (message.type === 'status') return { ...lastStatus, audio: session?.audio,
      audioStates: session ? [session.context?.state, session.monitor?.state] : [] };
    if (message.type === 'stop') { await session?.stop(); return { ok: true }; }
    if (message.type === 'start') {
      if (session) throw new Error('当前字幕尚未停止');
      const current = session = new Session(message);
      try { await current.start(); }
      catch (error) { await current.fail(error); throw error; }
      return { ok: true };
    }
  })().then(reply).catch(error => reply({ error: error.message }));
  return true;
});
