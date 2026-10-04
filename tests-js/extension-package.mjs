// Validate what users download, not the source extension directory.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { chromium } from 'playwright';

await test('Downloaded extension ZIP passes its checksum and loads its popup and audio capture resources in Chromium', async () => {
  const output = 'dist/extension';
  const files = (await readdir(output)).filter(name => name.endsWith('.zip'));
  assert.equal(files.length, 1, 'Expected a single versioned extension ZIP');
  const archive = path.resolve(output, files[0]);
  const digest = createHash('sha256').update(await readFile(archive)).digest('hex');
  assert.equal((await readFile(`${archive}.sha256`, 'utf8')).trim(), `${digest}  ${files[0]}`);
  const temporary = await mkdtemp(path.join(tmpdir(), 'tingsub-extension-package-'));
  let context;
  try {
    const extension = path.join(temporary, 'extension');
    execFileSync('python3', ['-m', 'zipfile', '-e', archive, extension]);
    const manifest = JSON.parse(await readFile(path.join(extension, 'manifest.json'), 'utf8'));
    assert.equal(files[0], `TingSub-extension-${manifest.version}.zip`);
    context = await chromium.launchPersistentContext(path.join(temporary, 'profile'), {
      channel: 'chromium', headless: true,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
    });
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    const id = new URL(worker.url()).host;
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`chrome-extension://${id}/${manifest.action.default_popup}`);
    assert.equal(await page.locator('#start').isVisible(), true);
    // Exercise Chrome's extension resource loader without starting tab capture or a service.
    const status = await page.evaluate(async () => {
      const paths = ['offscreen.html', 'offscreen.js', 'pcm-worklet.js', 'overlay.js', 'LICENSE'];
      return Promise.all(paths.map(async name => {
        const response = await fetch(chrome.runtime.getURL(name));
        return { name, ok: response.ok, size: (await response.text()).length };
      }));
    });
    assert.ok(status.every(resource => resource.ok && resource.size > 0), JSON.stringify(status));
    assert.deepEqual(errors, []);
  } finally {
    await context?.close();
    await rm(temporary, { recursive: true, force: true });
  }
});
