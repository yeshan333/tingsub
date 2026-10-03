import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, readdir, mkdir } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright";

execFileSync("python3", ["scripts/build_site.py"], { stdio: "inherit" });
const root = "dist/site";
const files = new Set(await readdir(root, { recursive: true }));
const mime = {
  html: "text/html; charset=utf-8",
  css: "text/css",
  js: "text/javascript",
  svg: "image/svg+xml",
  png: "image/png",
  xml: "application/xml",
};
const server = createServer(async (request, response) => {
  const path = new URL(request.url, "http://localhost").pathname;
  if (!path.startsWith("/tingsub/")) {
    response.writeHead(404).end();
    return;
  }
  const name =
    path.slice("/tingsub/".length) + (path.endsWith("/") ? "index.html" : "");
  if (!files.has(name)) {
    response.writeHead(404).end();
    return;
  }
  try {
    const data = await readFile(`${root}/${name}`);
    response.setHeader(
      "Content-Type",
      mime[name.split(".").pop()] || "application/octet-stream",
    );
    response.end(data);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/tingsub/`;
const browser = await chromium.launch();
await mkdir(".local/site", { recursive: true });
try {
  await test("Homepage works under the GitHub Pages project path in both languages", async () => {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    const failures = [];
    page.on("pageerror", (error) => failures.push(error.message));
    page.on("response", (response) => {
      if (response.status() >= 400) failures.push(response.url());
    });
    const requests = [];
    page.on("request", (request) => requests.push(request.url()));
    for (const [locale, path] of [
      ["zh-CN", ""],
      ["en", "en/"],
    ]) {
      await page.goto(base + path);
      assert.equal(await page.locator("html").getAttribute("lang"), locale);
      assert.equal(await page.locator("h1").count(), 1);
      assert.equal(
        await page.locator("link[rel=canonical]").getAttribute("href"),
        `https://yeshan333.github.io/tingsub/${path}`,
      );
      const links = await page
        .locator("a")
        .evaluateAll((elements) =>
          elements.map((element) => element.getAttribute("href")),
        );
      for (const href of links) {
        if (href.startsWith("#"))
          assert.equal(
            await page.locator(href).count(),
            1,
            `Anchor ${href} exists`,
          );
        if (
          href.startsWith("https://github.com/yeshan333/tingsub/blob/main/")
        ) {
          const localPath = href.split("/blob/main/")[1];
          assert.ok(
            (await readFile(localPath)).length,
            `Guide ${localPath} exists`,
          );
        }
      }
      await page.locator("[name=screen][value=models]").check();
      assert.equal(
        await page.locator("[data-screen=models]").isVisible(),
        true,
      );
      assert.equal(
        await page.locator("[data-screen=captions]").isVisible(),
        false,
      );
      await page.locator("[name=screen][value=captions]").check();
      // Load the real screenshot, including when below the initial viewport.
      await page.locator("[data-screen=captions]").scrollIntoViewIfNeeded();
      await page.waitForFunction(
        () =>
          document.querySelector("[data-screen=captions] img").naturalWidth ===
          1200,
      );
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({
        path: `.local/site/home-${locale}.png`,
        fullPage: true,
      });
      await page.locator(".language").click();
      assert.equal(
        await page.locator("html").getAttribute("lang"),
        locale === "en" ? "zh-CN" : "en",
      );
    }
    assert.deepEqual(failures, []);
    assert.ok(
      requests.every((url) => url.startsWith(base)),
      "The site loads no third-party scripts, fonts or tracking",
    );
    await page.close();
  });

  await test("Japanese sample shows original speech when translation is off and restores bilingual text when on", async () => {
    const page = await browser.newPage();
    await page.goto(base);
    await page.locator("[name=sample-language][value=ja]").check();
    assert.match(
      await page.locator(".sample-source q").textContent(),
      /海沿い/,
    );
    assert.equal(
      await page.locator(".caption-original").getAttribute("lang"),
      "en",
    );
      await page.locator(".translation-toggle").click();
    assert.equal(await page.locator(".caption-zh").isVisible(), false);
    assert.equal(
      await page.locator(".caption-original").getAttribute("lang"),
      "ja",
    );
    assert.match(
      await page.locator(".caption-original").textContent(),
      /海沿い/,
    );
    await page.locator("#translation").focus();
    await page.keyboard.press("Space");
    assert.equal(await page.locator(".caption-zh").isVisible(), true);
    assert.equal(
      await page.locator(".caption-original").getAttribute("lang"),
      "en",
    );
    await page.close();
  });

  await test("Small screens keep captions, installation and FAQ readable without horizontal scrolling", async () => {
    const page = await browser.newPage({ reducedMotion: "reduce" });
    for (const path of ["", "en/"]) {
      for (const width of [320, 390, 768]) {
        await page.setViewportSize({ width, height: 844 });
        await page.goto(base + path);
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          true,
          `${path || "zh"} at ${width}px fits`,
        );
        const caption = await page.locator(".caption").boundingBox();
        const scene = await page.locator(".scene").boundingBox();
        assert.ok(
          caption.x >= scene.x &&
            caption.y >= scene.y &&
            caption.y + caption.height <= scene.y + scene.height,
          "Sample captions remain within the scene",
        );
        await page.locator("summary").first().click();
        assert.equal(
          await page.locator("details").first().getAttribute("open"),
          "",
        );
        assert.equal(await page.locator(".setup .primary").isVisible(), true);
        if (width === 390)
          await page.screenshot({
            path: `.local/site/mobile-${path ? "en" : "zh"}.png`,
            fullPage: true,
          });
      }
    }
    await page.close();
  });

  await test("Without JavaScript, visitors can read both screenshots, open FAQs and switch languages", async () => {
    const page = await browser.newPage({ javaScriptEnabled: false });
    await page.goto(base);
    assert.equal(await page.locator(".demo-controls").isVisible(), false);
    assert.equal(await page.locator(".screen-controls").isVisible(), false);
    assert.equal(
      await page.locator("[data-screen=captions]").isVisible(),
      true,
    );
    assert.equal(await page.locator("[data-screen=models]").isVisible(), true);
    await page.locator("summary").first().click();
    assert.equal(
      await page.locator("details").first().getAttribute("open"),
      "",
    );
    await page.locator(".language").click();
    assert.equal(await page.locator("html").getAttribute("lang"), "en");
    assert.match(
      await page.locator(".hero .primary").getAttribute("href"),
      /docs\/en\/installation.md$/,
    );
    await page.close();
  });
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
