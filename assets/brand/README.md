# TingSub mark · 听桥标志

An open ear surrounds two caption lines; a terracotta full stop adds a quiet accent.
Pine green `#2e4036`, warm white `#eff1e5`, terracotta `#df9678`.
The menu bar uses the same silhouette in a monochrome macOS template image.

耳朵轮廓包住两行字幕，陶土色句点收尾。松绿、米白与现有界面一致；菜单栏使用同轮廓的单色模板图，跟随系统明暗外观。

`mark.svg` is the editable source. Rebuild the committed assets on macOS:

`mark.svg` 是可编辑源文件，在 macOS 上重新生成所有已提交的资源：

```sh
npm ci
npx playwright install chromium
node scripts/build_brand.mjs
```

- `TingSub.icns` / `app-icon.png`: macOS application, with transparent outer padding.
- `../../site/icon.svg`: homepage and favicon.
- `../../src/live_subs/desktop_ui/brand.svg` / `menubar.png`: desktop and 18 pt menu bar.
- `../../extension/icons/`: Chrome toolbar, extension manager and popup, 16–128 px.

The generator uses the existing development-only Playwright dependency and macOS `iconutil`.
Application builds consume the committed files; no browser or image renderer is added to the runtime.
Non-macOS hosts regenerate the web/PNG assets only. PNG/ICNS export is lossless; keep alpha intact.

生成脚本只用现有的开发依赖 Playwright 和 macOS 自带的 `iconutil`。应用构建直接使用已提交的文件，无须新增运行时依赖。非 macOS 系统仅生成网页与 PNG 资源，请保留透明通道。
