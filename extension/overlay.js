(() => {
  if (globalThis.__tingqiaoOverlay) return;
  globalThis.__tingqiaoOverlay = true;
  document.getElementById('tingqiao-local-captions')?.remove();
  const host = document.createElement('div');
  host.id = 'tingqiao-local-captions';
  host.style.cssText = 'position:fixed;inset:auto 4vw 8vh;z-index:2147483647;pointer-events:none;display:block;';
  const shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = `<style>
    :host{all:initial}*{box-sizing:border-box}.box{max-width:1000px;margin:0 auto;padding:12px 22px 18px;border:1px solid #ffffff26;border-radius:16px;background:#101c21eb;color:#fff;box-shadow:0 8px 40px #0004;font:16px/1.5 system-ui,-apple-system,"PingFang SC",sans-serif;pointer-events:auto;backdrop-filter:blur(10px)}
    header{display:flex;align-items:center;gap:10px;color:#a6c5bb;font-size:11px;cursor:grab;user-select:none;margin-bottom:8px}header:active{cursor:grabbing}.brand{letter-spacing:2px;white-space:nowrap}.state{flex:1;color:#93a7a1;overflow-wrap:anywhere}.close{color:#adc4bc;background:transparent;border:0;font:20px/1 system-ui;cursor:pointer;padding:2px 6px}.row{margin-top:10px}.row:not(:last-child){opacity:.55;font-size:.78em}.zh{font-size:var(--caption-size,26px);font-weight:600;line-height:1.5;color:#fff;white-space:pre-wrap;overflow-wrap:anywhere}.second{font-size:calc(var(--caption-size,26px) * .8);color:#c8e4dc;margin-top:3px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}.pending .second{color:#a4b5b0}.note{color:#8fa79e;font-size:11px;margin-top:3px}.empty{color:#9cb6ac;text-align:center;padding:6px;font-size:14px}
    @media(prefers-reduced-motion:no-preference){.row{transition:opacity .15s}}
  </style><section class="box" aria-label="听桥实时字幕"><header><span class="brand">TingSub · LOCAL</span><span class="state" role="status">等待直播音频…</span><button class="close" aria-label="停止字幕">×</button></header><div class="rows" aria-live="polite" aria-relevant="text additions"></div><div class="stats note"></div></section>`;
  const rows = shadow.querySelector('.rows');
  const state = shadow.querySelector('.state');
  const stats = shadow.querySelector('.stats');
  const captions = new Map();
  let floor = 0;
  let running = false;
  let lastUpdate = 0;

  function mount() {
    const parent = document.fullscreenElement || document.documentElement;
    if (host.parentNode !== parent) parent.appendChild(host);
  }
  function render() {
    rows.replaceChildren();
    if (!captions.size) {
      const empty = document.createElement('div'); empty.className = 'empty';
      empty.textContent = running ? '正在聆听，等待人声…' : '字幕已停止'; rows.appendChild(empty); return;
    }
    for (const caption of [...captions.values()].sort((a, b) => a.id - b.id)) {
      const row = document.createElement('div'); row.className = `row ${caption.type === 'translation' ? '' : 'pending'}`;
      row.dataset.id = caption.id;
      const zh = document.createElement('div'); zh.className = 'zh'; zh.textContent = caption.zh || '';
      const second = document.createElement('div'); second.className = 'second';
      second.textContent = caption.display === 'source-zh' ? caption.source : (caption.en || caption.source);
      const note = document.createElement('div'); note.className = 'note';
      if (caption.error) note.textContent = `翻译失败：${caption.error}`;
      else if (caption.type === 'translation_progress') note.textContent = '中文先行 · 正在完成双语结果';
      else if (caption.type !== 'translation') note.textContent = caption.final ? '本地翻译中…' : '识别草稿';
      row.append(zh, second, note); rows.appendChild(row);
    }
  }
  function receive(event) {
    if (event.metrics) {
      const c = event.metrics.counts || {};
      stats.textContent = `已译 ${c.translated || 0} · 低置信度 ${c.low_confidence || 0} · 重复异常 ${c.repetition || 0} · 无人声/空结果 ${(c.silence || 0) + (c.empty || 0)} · 过期 ${c.dropped || 0}`;
    }
    if (event.type === 'notice') { state.textContent = event.message; return; }
    if (event.type === 'reset') {
      captions.clear(); floor = 0; running = true; stats.textContent = '';
      host.style.display = 'block';
      host.style.setProperty('--caption-size', `${Math.max(18, Math.min(40, event.fontSize || 26))}px`);
      state.textContent = '正在连接本机模型…'; mount(); render(); return;
    }
    if (event.type === 'state') {
      running = ['running', 'starting', 'stopping'].includes(event.state);
      state.textContent = event.message;
      if (!running) { setTimeout(() => { if (!running) host.style.display = 'none'; }, 8000); }
      render(); return;
    }
    if (['dropped', 'empty', 'rejected'].includes(event.type)) {
      captions.delete(event.id); floor = Math.max(floor, event.id); render();
      if (event.message) state.textContent = event.message;
      return;
    }
    if (event.type === 'error') {
      state.textContent = event.message;
      if (captions.has(event.id)) { captions.get(event.id).error = event.message; render(); }
      return;
    }
    if (!['transcript', 'translation_progress', 'translation'].includes(event.type) || event.id <= floor) return;
    const previous = captions.get(event.id);
    if (previous?.type === 'translation' && event.type !== 'translation') return;
    if (previous?.type === 'translation_progress' && event.type === 'transcript') return;
    if (previous?.final && !event.final) return;
    const caption = { ...previous, ...event };
    if (event.speech_start_ms) {
      caption.firstText ??= Math.max(0, Date.now() - event.speech_start_ms);
      if (event.zh) caption.firstZh ??= Math.max(0, Date.now() - event.speech_start_ms);
    }
    captions.set(event.id, caption);
    while (captions.size > 2) {
      const oldest = Math.min(...captions.keys()); captions.delete(oldest); floor = Math.max(floor, oldest);
    }
    lastUpdate = Date.now();
    if (event.type === 'translation_progress') {
      state.textContent = `本段首个中文 ${(caption.firstZh / 1000).toFixed(1)}s · 正在补齐译文`;
    }
    if (event.type === 'translation') {
      const lag = Math.max(0, Date.now() - event.speech_end_ms);
      const first = caption.firstZh === undefined ? '' : `本段首字 ${(caption.firstText / 1000).toFixed(1)}s · 首中 ${(caption.firstZh / 1000).toFixed(1)}s · `;
      state.textContent = `${first}句尾 ${(lag / 1000).toFixed(1)}s · 识别 ${event.asr_ms}ms · 翻译 ${event.translation_ms}ms`;
    }
    mount(); render();
  }
  chrome.runtime.onMessage.addListener(message => {
    if (message.target === 'overlay') receive(message.event);
  });
  shadow.querySelector('.close').onclick = () => {
    chrome.runtime.sendMessage({ target: 'background', type: 'stop' }).catch(() => {});
    host.style.display = 'none';
  };
  document.addEventListener('fullscreenchange', mount);
  document.addEventListener('yt-navigate-start', () => {
    chrome.runtime.sendMessage({ target: 'background', type: 'stop' }).catch(() => {});
  });
  // Do not leave a stale line over a silent stream indefinitely.
  setInterval(() => {
    if (running && captions.size && Date.now() - lastUpdate > 15000) {
      const max = Math.max(...captions.keys()); floor = Math.max(floor, max); captions.clear(); render();
    }
  }, 1000);
  const header = shadow.querySelector('header');
  header.addEventListener('pointerdown', event => {
    if (event.target.closest('button')) return;
    const start = host.getBoundingClientRect();
    const dx = event.clientX - start.left, dy = event.clientY - start.top;
    header.setPointerCapture(event.pointerId);
    header.onpointermove = move => {
      host.style.left = `${Math.max(0, Math.min(innerWidth - 160, move.clientX - dx))}px`;
      host.style.top = `${Math.max(0, Math.min(innerHeight - 60, move.clientY - dy))}px`;
      host.style.right = 'auto'; host.style.bottom = 'auto'; host.style.width = `${start.width}px`;
    };
    header.onpointerup = () => { header.onpointermove = null; };
    header.onlostpointercapture = () => { header.onpointermove = null; };
  });
})();
