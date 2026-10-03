// Layout and update checks use explicit protocol data, not simulated inference.
import { chromium } from 'playwright';
import { readFile, mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setContent(`<style>body{margin:0;background:#ecece9;font:14px system-ui}main{width:960px;margin:90px 0 0 64px}#player{position:relative;width:100%;aspect-ratio:16/9;background:#485758}video{display:block;width:100%;height:100%;background:linear-gradient(150deg,#505c5c,#1a242b)}#player:fullscreen{width:100%;height:100%}.label{position:absolute;left:24px;top:24px;color:#eeece6;font-size:12px;letter-spacing:.08em}.content{height:1100px;padding:24px}</style><main><div id="player"><video></video><div class="label">TINGSub · 字幕样式测试 / 示例文字</div></div><div class="content">视频下方的页面内容</div></main>`);
  await page.evaluate(() => {
    window.chrome = { runtime: { onMessage: { addListener: callback => { window.receive = callback; } }, sendMessage: async () => ({}) } };
  });
  await page.addScriptTag({ content: await readFile('extension/overlay.js', 'utf8') });
  const send = event => page.evaluate(event => window.receive({ target: 'overlay', event }), event);
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const bounds = async () => page.evaluate(() => {
    const rect = element => { const r = element.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
    return { video: rect(document.querySelector('video')), overlay: rect(document.getElementById('tingqiao-local-captions')) };
  });
  await send({ type: 'reset', fontSize: 26 });
  await send({ type: 'translation', id: 1, zh: '世界很大，慢慢听。', en: "There’s a whole world out there. Take it in.", final: true });
  await settle();
  let rect = await bounds();
  assert.ok(rect.overlay.x >= rect.video.x && rect.overlay.right <= rect.video.right);
  assert.ok(rect.overlay.bottom < rect.video.bottom - 30, '字幕应留出播放器底部控件的空间');
  assert.ok(rect.overlay.height < 160, '正常双语句子不应占用多段字幕和调试面板的高度');
  assert.equal(await page.locator('.diagnostics').isVisible(), false);
  const row = await page.locator('.row').elementHandle();
  await send({ type: 'transcript', id: 2, source: 'The next sentence is still forming', final: false });
  assert.equal(await page.locator('.zh').textContent(), '世界很大，慢慢听。');
  assert.equal(await page.locator('.draft').textContent(), '识别中 · The next sentence is still forming');
  await send({ type: 'translation_progress', id: 2, zh: '下一句开始了。', final: true });
  assert.equal(await row.evaluate(node => node.isConnected), true, '更新复用字幕节点，不重建已显示的内容树');
  assert.equal(await page.locator('.zh').textContent(), '下一句开始了。');
  assert.equal(await page.locator('.draft').textContent(), '');
  await send({ type: 'translation', id: 2, zh: '下一句开始了。', en: 'The next sentence begins.', final: true });
  await page.mouse.move(1400, 10);
  await settle();
  await mkdir('.local', { recursive: true });
  await page.screenshot({ path: '.local/overlay-video.png' });

  await page.evaluate(() => scrollTo(0, 60));
  await settle();
  const scrolled = await bounds();
  assert.ok(Math.abs(scrolled.overlay.y - rect.overlay.y + 60) < 2, '滚动页面时字幕跟随视频');
  await page.locator('.surface').hover();
  await page.locator('.details').click();
  assert.equal(await page.locator('.diagnostics').isVisible(), true);
  await page.locator('.details').click();
  await page.locator('.surface').hover();
  const header = await page.locator('.brand').boundingBox();
  await page.mouse.move(header.x + 12, header.y + 6);
  await page.mouse.down();
  await page.mouse.move(1400, 850, { steps: 5 });
  await page.mouse.up();
  await settle();
  const dragged = (await bounds()).overlay;
  assert.ok(dragged.right <= 1428 && dragged.bottom <= 888, '拖动不能把字幕或操作按钮移出窗口');
  await page.locator('.surface').hover();
  await page.locator('.recenter').click();
  await settle();
  rect = await bounds();
  assert.ok(rect.overlay.right <= rect.video.right && rect.overlay.bottom < rect.video.bottom);

  await page.setViewportSize({ width: 500, height: 700 });
  await page.evaluate(() => { document.querySelector('main').style.cssText = 'width:calc(100% - 32px);margin:40px 16px 0'; scrollTo(0, 0); });
  const long = '这是一段需要自动换行的中文字幕，所有内容都应该保留。'.repeat(5);
  await send({ type: 'translation', id: 3, zh: long, en: 'A long English sentence that should wrap without overflowing the video. '.repeat(4), final: true });
  await settle();
  assert.equal(await page.locator('.zh').textContent(), long);
  rect = await bounds();
  assert.ok(rect.overlay.x >= 0 && rect.overlay.right <= 500 && rect.overlay.bottom <= 700);
  for (const selector of ['.zh', '.second']) {
    assert.ok(await page.locator(selector).evaluate(el => el.getBoundingClientRect().height + .1 >= parseFloat(getComputedStyle(el).lineHeight)), '每种语言至少保留一整行');
    const language = await page.locator(selector).boundingBox();
    assert.ok(language.y + language.height <= rect.overlay.bottom, '英文和中文必须同时可见');
  }
  await page.locator('.expand').click();
  assert.equal(await page.locator('.expand').getAttribute('aria-expanded'), 'true');
  await page.locator('.expand').click();
  await page.screenshot({ path: '.local/overlay-narrow.png' });
  await page.evaluate(() => { document.querySelector('#player').style.height = '185px'; });
  await settle();
  for (const selector of ['.zh','.second','.expand']) assert.equal(await page.locator(selector).isVisible(),true);
  let compact = await bounds();
  assert.ok(compact.overlay.bottom <= compact.video.bottom, '小播放器的正文和操作按钮不能越出视频');
  await page.locator('.surface').hover();
  await page.locator('.details').click();
  await settle();
  compact = await bounds();
  assert.ok(compact.overlay.bottom <= compact.video.bottom, '信息面板展开后仍必须留在小播放器内');
  await page.locator('.details').click();
  await page.evaluate(() => { document.querySelector('#player').style.height = ''; });
  await page.locator('#player').click({ position: { x: 5, y: 5 } });
  await page.evaluate(() => document.getElementById('player').requestFullscreen());
  await page.waitForFunction(() => document.getElementById('tingqiao-local-captions').parentElement.id === 'player');
  await settle();
  await page.evaluate(() => document.exitFullscreen());
  await page.setViewportSize({width:1440,height:900});
  await page.evaluate(() => scrollTo(0, 1000));
  await settle();
  assert.equal(await page.locator('#tingqiao-local-captions').isVisible(), false, '视频离开屏幕后字幕不能漂到网页其他内容上');

  const embedded = await browser.newPage({viewport:{width:1440,height:900}});
  await embedded.setContent('<iframe style="width:1100px;height:700px;border:0" srcdoc="<div style=height:50px>房间信息</div><video style=width:800px;height:450px></video><aside>右侧聊天</aside>"></iframe>');
  const init = () => { window.chrome = {runtime:{onMessage:{addListener:callback=>{window.receive=callback;}},sendMessage:async()=>({})}}; };
  await embedded.evaluate(init);
  await embedded.addScriptTag({content:await readFile('extension/overlay.js','utf8')});
  const child = embedded.frames().find(frame=>frame.parentFrame());
  await child.evaluate(init);
  await child.addScriptTag({content:await readFile('extension/overlay.js','utf8')});
  for (const frame of [embedded.mainFrame(),child]) {
    await frame.evaluate(() => { window.receive({target:'overlay',event:{type:'reset'}}); window.receive({target:'overlay',event:{type:'translation',id:1,zh:'嵌入播放器内的字幕',en:'Captions inside the embedded player',final:true}}); });
  }
  await embedded.waitForFunction(() => document.querySelector('#tingqiao-local-captions').style.visibility === 'hidden');
  assert.equal(await child.locator('#tingqiao-local-captions').isVisible(),true);
  assert.ok(await child.locator('#tingqiao-local-captions').evaluate(node=>node.getBoundingClientRect().right <= document.querySelector('video').getBoundingClientRect().right), '字幕必须在视频宽度内，不能覆盖 iframe 内的聊天区');
  await embedded.close();
  assert.deepEqual(errors, []);
  console.log('通过：视频内定位、保留译文等待新草稿、节点复用、滚动跟随、按需信息、拖动边界与归位、窄屏长句、全屏。');
} finally { await browser.close(); }
