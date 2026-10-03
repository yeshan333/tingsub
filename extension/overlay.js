(() => {
  // allFrames can also reach hosts covered by permanent permissions (loopback).
  // Never expose caption text to an embedded page from a different origin.
  if (window !== window.top && location.ancestorOrigins[location.ancestorOrigins.length - 1] !== location.origin) return;
  if (globalThis.__tingqiaoOverlay) return;
  globalThis.__tingqiaoOverlay = true;
  document.getElementById('tingqiao-local-captions')?.remove();
  const host = document.createElement('div');
  host.id = 'tingqiao-local-captions';
  host.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;display:block;';
  const shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = `<style>
    :host{all:initial}*{box-sizing:border-box}[hidden]{display:none!important}
    .box{position:relative;margin:0 auto;color:#fff;font:14px/1.4 system-ui,-apple-system,"PingFang SC",sans-serif;text-align:center;pointer-events:none}
    .surface{display:inline-block;max-width:100%;min-width:min(360px,100%);padding:10px 18px 8px;border-radius:8px;background:#121416c9;box-shadow:0 2px 12px #0003;text-shadow:0 1px 3px #0008;pointer-events:auto}
    header{display:flex;align-items:center;gap:6px;width:max-content;max-width:100%;margin:0 auto 6px;padding:3px 5px 3px 10px;border-radius:6px;background:#17191ef2;color:#d0d2d6;font-size:11px;cursor:grab;user-select:none;pointer-events:none;opacity:0;transition:opacity .15s}
    .box:hover header,.box:focus-within header,.box.idle header{opacity:1;pointer-events:auto}header:active{cursor:grabbing}.brand{letter-spacing:.03em;white-space:nowrap;margin-right:6px}.state{display:none}
    button{color:inherit;background:transparent;border:0;border-radius:4px;font:inherit;cursor:pointer;padding:5px 7px;white-space:nowrap}button:hover,button[aria-expanded=true]{background:#ffffff20}button:focus-visible{outline:2px solid #d8d6cb;outline-offset:1px}.close{font-size:19px;padding:0 7px}
    .zh{font-size:var(--caption-size,26px);font-weight:600;line-height:1.42;min-height:1.42em;color:#fff;white-space:pre-wrap;overflow-wrap:anywhere;text-wrap:pretty;max-height:2.84em;overflow:auto}
    .second{font-size:calc(var(--caption-size,26px)*.76);font-weight:400;color:#dedfe3;margin-top:4px;line-height:1.4;min-height:1.4em;white-space:pre-wrap;overflow-wrap:anywhere;text-wrap:pretty;max-height:2.8em;overflow:auto}
    .compact:not(.expanded) .zh{max-height:1.42em}.compact:not(.expanded) .second{max-height:1.4em}.compact .draft{display:none}.details-open .surface,.compact.has-error .surface{display:none}.expanded .zh,.expanded .second{max-height:var(--language-height,120px)}.expand{font-size:11px;color:#d0d2d6;padding:2px 7px;margin-top:4px}.pending .second{color:#c6c8ce}.note{font-size:11px;color:#c3c5ca;margin-top:5px}.note:empty{display:none}.note.error{color:#ffd2c9}
    .draft{height:22px;margin-top:5px;font-size:12px;line-height:22px;color:#bfc3ca;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.draft:empty{height:0;margin-top:0}
    .empty{font-size:12px;color:#c6c8ce;padding:0 4px}.status-message{font-size:12px;color:#fff1cb;margin-bottom:6px;padding:5px 10px;background:#17191ee6;border-radius:5px;pointer-events:auto;max-height:36px;overflow:auto}
    .surface:focus-visible{outline:2px solid #d8d6cb;outline-offset:2px}.diagnostics{max-height:var(--info-height,120px);overflow-y:auto;margin:6px auto 0;padding:8px 12px;border-radius:6px;background:#17191ef2;font-size:11px;line-height:1.6;color:#c7c9cf;text-align:left;pointer-events:auto;overflow-wrap:anywhere}.diagnostics .state{display:block}.stats:empty{display:none}
    @media(prefers-reduced-motion:reduce){header{transition:none}}
  </style><section class="box idle" aria-label="TingSub 双语字幕"><header><span class="brand" title="拖动可移动字幕">⠿ TingSub</span><button class="recenter" aria-label="字幕回到视频底部">归位</button><button class="details" aria-expanded="false" aria-label="显示运行信息">信息</button><button class="close" aria-label="停止字幕">×</button></header><div class="status-message" role="status" hidden></div><div class="surface" tabindex="0" aria-label="字幕内容"><div class="rows" aria-live="polite" aria-relevant="text additions"></div><div class="draft" aria-label="下一句识别草稿"></div><button class="expand" hidden aria-expanded="false">展开长句</button></div><div class="diagnostics" hidden><div class="state">等待直播音频…</div><div class="stats"></div></div></section>`;
  const rows = shadow.querySelector('.rows');
  const state = shadow.querySelector('.state');
  const stats = shadow.querySelector('.stats');
  const captions = new Map();
  const box = shadow.querySelector('.box');
  const draft = shadow.querySelector('.draft');
  const statusMessage = shadow.querySelector('.status-message');
  let manualPosition = null;
  let geometryFrame = 0;
  let trackedVideo;
  let hadVideo = false;
  let floor = 0;
  let running = false;
  let lastUpdate = 0;

  function videoBounds() {
    const videos = [...document.querySelectorAll('video')].filter(video => {
      const rect = video.getBoundingClientRect();
      return rect.width >= 160 && rect.height >= 90 && rect.bottom > 0 && rect.right > 0 && rect.top < innerHeight && rect.left < innerWidth;
    });
    videos.sort((a, b) => {
      const weight = video => { const r = video.getBoundingClientRect(); return r.width * r.height * (!video.paused ? 2 : 1); };
      return weight(b) - weight(a);
    });
    const video = videos[0];
    if (video !== trackedVideo) {
      if (trackedVideo) resizeObserver.unobserve(trackedVideo);
      trackedVideo = video;
      if (video) resizeObserver.observe(video);
    }
    if (!video) {
      // Never turn a scrolled-away player into a page-wide caption card.
      const embedded = [...document.querySelectorAll('iframe')].some(frame => {
        const r = frame.getBoundingClientRect(); return r.width >= 320 && r.height >= 180;
      });
      if (hadVideo || window !== window.top || embedded) return null;
      return { left: 0, top: 0, right: innerWidth, bottom: innerHeight, width: innerWidth, height: innerHeight };
    }
    hadVideo = true;
    const rect = video.getBoundingClientRect();
    const left = Math.max(0, rect.left), top = Math.max(0, rect.top);
    const right = Math.min(innerWidth, rect.right), bottom = Math.min(innerHeight, rect.bottom);
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  }
  function position() {
    geometryFrame = 0;
    const bounds = videoBounds();
    host.style.visibility = bounds && bounds.height >= 180 && bounds.width >= 200 ? 'visible' : 'hidden';
    if (!bounds) return;
    box.classList.toggle('compact', bounds.height < 320);
    box.classList.toggle('has-error', !statusMessage.hidden);
    host.style.setProperty('--info-height', `${Math.max(40, Math.min(120, bounds.height - 100))}px`);
    const width = Math.max(120, Math.min(860, bounds.width - 32, innerWidth - 24));
    host.style.width = `${width}px`;
    host.style.setProperty('--caption-max-height', `${Math.max(100, bounds.height - 100)}px`);
    host.style.setProperty('--language-height', `${Math.max(bounds.height < 320 ? 30 : fontSize * 2.84, (bounds.height - 190) / 2)}px`);
    // Scale the chosen font down only when the player itself is narrow.
    host.style.setProperty('--caption-size', `${Math.min(fontSize, bounds.height < 260 ? 18 : 40, Math.max(18, bounds.width / 27))}px`);
    const height = host.getBoundingClientRect().height;
    const x = manualPosition ? manualPosition.x * Math.max(0, innerWidth - width) : bounds.left + (bounds.width - width) / 2;
    const y = manualPosition ? manualPosition.y * Math.max(0, innerHeight - height) : bounds.bottom - (bounds.height < 320 ? 24 : Math.min(84, Math.max(40, bounds.height * .12))) - height;
    host.style.left = `${Math.max(12, Math.min(innerWidth - width - 12, x))}px`;
    host.style.top = `${Math.max(manualPosition ? 12 : bounds.top + 8, Math.min(innerHeight - height - 12, y))}px`;
    const expand = shadow.querySelector('.expand');
    expand.hidden = !box.classList.contains('expanded') && ![...rows.querySelectorAll('.zh,.second')].some(el => el.scrollHeight > el.clientHeight + 1);
  }
  function schedulePosition() {
    if (!geometryFrame) geometryFrame = requestAnimationFrame(position);
  }
  const resizeObserver = new ResizeObserver(schedulePosition);
  resizeObserver.observe(host);
  let fontSize = 26;
  function mount() {
    const parent = document.fullscreenElement || document.documentElement;
    if (host.parentNode !== parent) parent.appendChild(host);
    schedulePosition();
  }
  function render() {
    const ordered = [...captions.values()].sort((a, b) => a.id - b.id);
    const latest = ordered.at(-1);
    // Keep the translated sentence readable while the next ASR draft is forming.
    const caption = latest?.translate === false || latest?.zh || latest?.error ? latest : ordered.findLast(item => item.zh) || latest;
    box.classList.toggle('idle', !caption);
    if (!caption) {
      if (!rows.querySelector('.empty')) {
        rows.replaceChildren();
        const empty = document.createElement('div'); empty.className = 'empty'; rows.appendChild(empty);
      }
      rows.firstChild.textContent = running ? '正在聆听，等待人声…' : '字幕已停止';
      draft.textContent = ''; schedulePosition(); return;
    }
    let row = rows.querySelector('.row');
    if (!row) {
      row = document.createElement('div');
      row.innerHTML = '<div class="zh"></div><div class="second"></div><div class="note"></div>';
      rows.replaceChildren(row);
    }
    row.className = `row ${caption.type === 'translation' ? '' : 'pending'}`;
    if (row.dataset.id !== String(caption.id)) { row.querySelectorAll('.zh,.second').forEach(el => { el.scrollTop = 0; }); box.classList.remove('expanded'); shadow.querySelector('.expand').setAttribute('aria-expanded', 'false'); shadow.querySelector('.expand').textContent = '展开长句'; }
    row.dataset.id = caption.id;
    const zh = row.querySelector('.zh'), second = row.querySelector('.second'), note = row.querySelector('.note');
    const sourceOnly = caption.translate === false;
    const sameChinese = caption.language === 'zh' && Boolean(caption.zh);
    const text = sourceOnly ? '' : caption.display === 'source-zh' ? (sameChinese ? '' : caption.source) : caption.en || (sameChinese ? '' : caption.source);
    second.hidden = sourceOnly || (!text && Boolean(caption.zh));
    const primary = sourceOnly ? caption.source || '' : caption.zh || '';
    if (zh.textContent !== primary) zh.textContent = primary;
    if (second.textContent !== (text || '')) second.textContent = text || '';
    note.classList.toggle('error', Boolean(caption.error));
    note.textContent = caption.error ? `翻译失败：${caption.error}` : sourceOnly ? caption.final ? '' : '识别中…' : !caption.zh ? caption.final ? '正在翻译…' : '识别中…' : sameChinese && caption.display !== 'source-zh' && !caption.en && caption.type !== 'translation' ? '正在翻译英文…' : '';
    draft.textContent = latest !== caption && latest.source ? '识别中 · ' + latest.source : '';
    schedulePosition();
  }
  function receive(event) {
    if (event.metrics) {
      const c = event.metrics.counts || {};
      stats.textContent = `仅识别 ${c.transcribed || 0} · 已译 ${c.translated || 0} · 低置信度 ${c.low_confidence || 0} · 重复异常 ${c.repetition || 0} · 无人声/空结果 ${(c.silence || 0) + (c.empty || 0)} · 过期 ${c.dropped || 0}`;
    }
    if (event.type === 'notice') { state.textContent = event.message; return; }
    if (event.type === 'reset') {
      captions.clear(); floor = 0; running = true; stats.textContent = '';
      host.style.display = 'block';
      fontSize = Math.max(18, Math.min(40, event.fontSize || 26));
      statusMessage.hidden = true; lastUpdate = 0;
      state.textContent = '正在连接本机模型…'; mount(); render(); return;
    }
    if (event.type === 'state') {
      running = ['running', 'starting', 'stopping'].includes(event.state);
      state.textContent = event.message;
      statusMessage.hidden = event.state !== 'error';
      statusMessage.textContent = event.state === 'error' ? event.message : '';
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
      if (!captions.has(event.id)) { statusMessage.textContent = event.message; statusMessage.hidden = false; }
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
    statusMessage.hidden = true;
    if (event.type === 'translation_progress') {
      state.textContent = `本段首个中文 ${(caption.firstZh / 1000).toFixed(1)}s · 正在补齐译文`;
    }
    if (event.type === 'translation') {
      const lag = Math.max(0, Date.now() - event.speech_end_ms);
      const first = caption.firstZh === undefined ? '' : `本段首字 ${(caption.firstText / 1000).toFixed(1)}s · 首中 ${(caption.firstZh / 1000).toFixed(1)}s · `;
      state.textContent = event.translate === false ? `仅识别 · 识别 ${event.asr_ms}ms` : `${first}句尾 ${(lag / 1000).toFixed(1)}s · 识别 ${event.asr_ms}ms · 翻译 ${event.translation_ms}ms`;
    }
    mount(); render();
  }
  chrome.runtime.onMessage.addListener(message => {
    if (message.target === 'overlay') receive(message.event);
  });
  shadow.querySelector('.expand').onclick = event => {
    const expanded = box.classList.toggle('expanded');
    event.currentTarget.textContent = expanded ? '收起' : '展开长句';
    event.currentTarget.setAttribute('aria-expanded', String(expanded));
    schedulePosition();
  };
  shadow.querySelector('.close').onclick = () => {
    chrome.runtime.sendMessage({ target: 'background', type: 'stop' }).catch(() => {});
    host.style.display = 'none';
  };
  document.addEventListener('fullscreenchange', () => { manualPosition = null; mount(); });
  window.addEventListener('resize', schedulePosition);
  document.addEventListener('scroll', schedulePosition, true);
  shadow.querySelector('.recenter').onclick = () => { manualPosition = null; schedulePosition(); };
  shadow.querySelector('.details').onclick = event => {
    const panel = shadow.querySelector('.diagnostics'); panel.hidden = !panel.hidden;
    box.classList.toggle('details-open', !panel.hidden);
    event.currentTarget.setAttribute('aria-expanded', String(!panel.hidden)); schedulePosition();
  };
  document.addEventListener('yt-navigate-start', () => {
    chrome.runtime.sendMessage({ target: 'background', type: 'stop' }).catch(() => {});
  });
  // Do not leave a stale line over a silent stream indefinitely.
  setInterval(() => {
    if (running) schedulePosition();
    if (running && captions.size && Date.now() - lastUpdate > 15000) {
      const max = Math.max(...captions.keys()); floor = Math.max(floor, max); captions.clear(); render();
    }
  }, 1000);
  const header = shadow.querySelector('header');
  header.addEventListener('pointerdown', event => {
    if (event.target.closest('button')) return;
    event.preventDefault();
    const start = host.getBoundingClientRect();
    const dx = event.clientX - start.left, dy = event.clientY - start.top;
    header.setPointerCapture(event.pointerId);
    header.onpointermove = move => {
      const availableX = Math.max(0, innerWidth - host.offsetWidth);
      const availableY = Math.max(0, innerHeight - host.offsetHeight);
      manualPosition = {
        x: availableX ? Math.max(0, Math.min(1, (move.clientX - dx) / availableX)) : 0,
        y: availableY ? Math.max(0, Math.min(1, (move.clientY - dy) / availableY)) : 0,
      };
      schedulePosition();
    };
    header.onpointerup = () => { header.onpointermove = null; };
    header.onlostpointercapture = () => { header.onpointermove = null; };
  });
})();
