[English](../en/development.md) · [简体中文](../zh-CN/development.md) · [Index](README.md)

# 开发指南

## 复现工作区

完整开发环境使用 uv 管理的 Python 3.12、Node.js 22+ 与 Apple Silicon macOS。依赖分别固定在 `uv.lock` 和 `package-lock.json`。

```sh
uv sync --frozen --python 3.12
npm ci
uv run --frozen ruff check src tests scripts
uv run --frozen pytest -v
python3 scripts/check_docs.py
npm run check
npm test
npx playwright install chromium
npm run test:browser
npm run test:desktop
```

这些检查不下载模型权重，也不需要启动推理服务。Python 测试用明确的假引擎验证契约，浏览器渲染测试注入协议用例，都不衡量识别准确率。Playwright 使用独立浏览器配置，不修改日常 Chrome；截图保存在已忽略的 `.local/`。

## 真实推理

按照[安装指南](installation.md)准备模型并启动服务。性能测试前停止已有字幕会话，具体命令见[性能验证](benchmarks.md)。直接加载模型的检查需要先停止服务，避免多个进程争用 GPU。

## CI

GitHub Actions 在 macOS ARM64 执行 Python 静态检查、单元测试与包构建，在 Linux 执行 JavaScript、独立 Chromium 和文档检查。工作流仅具备只读权限，Actions 固定到提交哈希，依赖锁文件入库，不下载模型权重。上传的扩展压缩包只包含扩展源码。CI 通过说明逻辑、打包及渲染检查通过，不代表验证了 Metal 推理或自然直播准确率。

## 修改流程

1. Fork 后从 `main` 创建聚焦单一目标的分支。
2. 修改实现；行为变化时增加有意义的回归覆盖。
3. 执行上述相关检查；协议变化同时检查服务端与扩展。
4. 同步更新中英文文档；用户可见改动也更新两份变更记录。
5. 提交 PR，说明触发条件、新行为及实际完成的验证。

不要提交 `.local`、配对码、模型快照、私人音频、转写或浏览器配置。引入云端回退、遥测或扩大扩展权限前，需要明确的设计讨论。请阅读[贡献指南](../../CONTRIBUTING.zh-CN.md)和[安全政策](../../SECURITY.zh-CN.md)。

## 依赖更新

有意更新 Python 依赖时使用 `uv lock`，JavaScript 使用 `npm install`，检查并同时提交清单与锁文件。之后执行 `uv sync --frozen` 和 `npm ci`。Python 包与扩展版本应保持一致。模型变化还需要核对许可及真实模型检查；`prepare` 的自定义参数不保证任意 checkpoint 都兼容。

## 文档国际化

根目录 `README.md` 和政策文件为英文，`.zh-CN.md` 为简体中文。指南以同名文件分布在 `docs/en/` 与 `docs/zh-CN/`，顶部提供语言切换。两种语言必须包含一致的命令、支持范围、限制及许可信息。`scripts/check_docs.py` 检查页面成对与仓库内链接目标，不判断翻译质量，也不检查远程链接。文档国际化目前不等于扩展界面已国际化。

## 桌面验证

`npm run test:desktop` 使用明确的桌面桥接夹具验证控件调用、共享参数、外部服务保护、双语主题及最小窗口布局，不代表真实模型推理。截图保存在 `.local/desktop-*.png`。

原生 WebKit 冒烟检查需先安装桌面依赖、准备模型，并停止已有服务：

```sh
uv run --frozen --extra desktop python scripts/check_desktop_native.py
```

该检查打开独立原生窗口，点击真实界面的启动／停止控件，等待模型预热，验证本机接口可用并确认停止后端口释放。退出会清理其启动的服务，不采集浏览器音频。此项不在 CI 下载模型运行。

原生检查也验证外部 URL 导航被拒绝。仅检查 WebKit 界面和导航边界、不加载模型时，可追加 `--no-inference`。
