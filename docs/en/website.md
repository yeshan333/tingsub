[English](../en/website.md) · [简体中文](../zh-CN/website.md) · [Index](README.md)

# Product homepage

The GitHub Pages site is built from `site/` without a frontend framework or third-party requests. Chinese is at `/tingsub/`, English at `/tingsub/en/`. Both pages are rendered as HTML; language switching, documentation links, screenshots and FAQs work without JavaScript.

## Edit and preview

- `site/content.json`: paired Chinese and English copy. Keep product claims aligned with the implementation and release status.
- `site/index.html`, `style.css`, `site.js`: shared layout, styling and optional sample interactions.
- `scripts/build_site.py`: standard-library Python builder. Output defaults to ignored `dist/site`.
- `docs/assets/screenshots/`: actual desktop UI rendered with sample state. See the screenshot command in the main README.

```sh
python3 scripts/build_site.py
python3 -m http.server 8080 --directory dist
```

Open `http://localhost:8080/site/`. Do not serve the repository root: it may contain local model configuration or pairing secrets. The builder accepts `--output PATH` and `--site-url https://host/project` for a different publication URL. Relative assets support project subpaths; canonical/hreflang/social metadata and the sitemap use `--site-url`.

The illustrated caption demo uses authored text, not an audio stream or a model. Japanese with translation enabled shows Chinese + English; disabling translation exposes the Japanese original. Do not present these samples or desktop screenshots as live transcription or performance evidence.

## Check and publish

```sh
npm ci
npx playwright install chromium
npm run test:site
```

Tests build and serve the site under `/tingsub/`, verify both languages, guide links, keyboard-controlled translation, screenshot switching, 320/390/768 px layouts and no-JavaScript use. Rendered previews go to `.local/site/`; CI retains them as `homepage-previews` artifacts.

In repository **Settings → Pages**, select **GitHub Actions** as the source. `.github/workflows/pages.yml` builds and tests pull requests but only deploys from `main`. A merge that changes site inputs triggers publication; **Run workflow** on `main` can republish. The `github-pages` environment and Pages deployment permissions are confined to the deployment job. Only `dist/site` is uploaded, never the checkout or application data.

Expected URL: <https://shansan.top/tingsub/>. If the repository or domain changes, update the builder's default URL and the expected canonical URLs in the browser test. Do not add a root-domain `robots.txt` policy from this project subdirectory; `sitemap.xml` is available within the site.

## Copy and positioning

The product context in `.agents/product-marketing.md` records audience, evidence and current limitations. The original guidance was [product-marketing](https://github.com/coreyhaines31/marketingskills/tree/main/skills/product-marketing), [copywriting](https://github.com/coreyhaines31/marketingskills/tree/main/skills/copywriting) and [cro](https://github.com/coreyhaines31/marketingskills/tree/main/skills/cro).

The primary action downloads the latest Release DMG, with a separate Chrome extension download. Setup instructions, release notes and the notarization limitation remain visible. Keep asset names stable; update both languages and FAQs when minimum system requirements change. Code is MIT; model licenses remain separate. Never add invented customer counts, testimonials, accuracy or universal latency claims.
