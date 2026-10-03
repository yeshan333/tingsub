[English](../en/website.md) · [简体中文](../zh-CN/website.md) · [索引](README.md)

# 产品主页

GitHub Pages 主页由 `site/` 构建，不使用前端框架，也不请求第三方资源。中文页面位于 `/tingsub/`，英文位于 `/tingsub/en/`。两种语言都生成完整 HTML；禁用 JavaScript 后仍可切换语言、阅读截图、展开 FAQ 和访问文档。

## 修改与预览

- `site/content.json`：成对的中英文文案。产品描述需与实现和发布状态一致。
- `site/index.html`、`style.css`、`site.js`：共享页面结构、样式及可选交互。
- `scripts/build_site.py`：只依赖 Python 标准库的构建器，默认输出到已忽略的 `dist/site`。
- `docs/assets/screenshots/`：使用示例状态渲染的真实桌面界面。更新命令见主 README。

```sh
python3 scripts/build_site.py
python3 -m http.server 8080 --directory dist
```

打开 `http://localhost:8080/site/`。不要直接将仓库根目录作为静态服务目录，其中可能包含本地模型配置或配对密钥。构建器支持 `--output PATH` 和 `--site-url https://host/project`。资源使用相对路径，兼容项目子目录；canonical、hreflang、分享元数据和 sitemap 使用 `--site-url`。

海岸插画中的字幕是预设文字，不调用音频或模型。日语样例开启翻译时显示中文＋英文，关闭后显示日语原文。不能将样例或桌面截图用作实时识别、性能测量的证据。

## 检查与发布

```sh
npm ci
npx playwright install chromium
npm run test:site
```

测试会构建页面并挂载到 `/tingsub/`，检查两种语言、文档链接、键盘切换翻译、截图切换、320/390/768 px 布局以及禁用 JavaScript 的场景。渲染截图保存在 `.local/site/`，CI 将它们保存为 `homepage-previews` 制品。

在仓库 **Settings → Pages** 将来源设为 **GitHub Actions**。`.github/workflows/pages.yml` 为 PR 构建和测试，但只从 `main` 发布。影响主页的改动合并后自动上线，也可在 `main` 手动 **Run workflow** 重新发布。`github-pages` 环境和 Pages 写权限仅用于部署 job。上传范围仅为 `dist/site`，不包含源码仓库或应用数据。

预期地址：<https://shansan.top/tingsub/>。如果迁移仓库或更换域名，请同步修改构建器默认 URL 及浏览器测试中的 canonical 预期。项目子目录不提供域名根目录级别的 `robots.txt` 策略；站点内提供 `sitemap.xml`。

## 文案与定位

`.agents/product-marketing.md` 记录了受众、事实依据和当前限制。本次采用了 [product-marketing](https://github.com/coreyhaines31/marketingskills/tree/main/skills/product-marketing)、[copywriting](https://github.com/coreyhaines31/marketingskills/tree/main/skills/copywriting) 和 [cro](https://github.com/coreyhaines31/marketingskills/tree/main/skills/cro) 的指导。

当前主按钮指向源码安装指南。公开安装包发布后，应同时更新两种语言的入口、系统要求和 FAQ。代码的 MIT 许可不涵盖模型权重，不添加虚构用户数、评价、准确率或通用延迟承诺。
