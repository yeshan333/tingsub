[English](../en/distribution.md) · [简体中文](../zh-CN/distribution.md) · [索引](README.md)

# macOS 独立应用分发

用户打开 DMG 并将 TingSub 拖入 Applications 即可，不需要安装 Python、uv、Homebrew 或下载源码。首次使用在界面中下载模型、按引导配对 Chrome，见[桌面指南](desktop.md)。App 在 DMG 压缩前约 1 GB；模型缓存另计，不随安装包附带。

## 下载 Release

直接下载 [macOS 应用（DMG）](https://github.com/yeshan333/tingsub/releases/latest/download/TingSub-macos-arm64.dmg)、[浏览器插件](https://github.com/yeshan333/tingsub/releases/latest/download/TingSub-extension.zip)，或查看 [Release 全部附件和版本说明](https://github.com/yeshan333/tingsub/releases/latest)。公开 Release 附件无需登录 GitHub，不受 Actions 制品 30 天保留期限制。

应用支持 **Apple Silicon / macOS 15+**，内嵌运行环境，无需安装 Python、uv 或 Homebrew。打开 DMG，将 TingSub 拖入 Applications；也可选择 `.app.zip`。当前为早期版本，**未经 Apple Developer ID 签名或公证**，系统可能提示无法验证开发者。首次使用通过界面下载模型。

插件 ZIP 解压到固定目录，在 `chrome://extensions` 开启开发者模式并「加载已解压的扩展程序」，选择含 `manifest.json` 的目录；也可使用 App 内「打开插件文件夹」。更新时替换原目录文件并重新加载，保留配对设置。尚未上架 Chrome 商店。

下载全部三个压缩包和 `SHA256SUMS` 到同一目录后，可运行 `shasum -a 256 -c SHA256SUMS` 校验。仅下载部分文件时，使用 `shasum -a 256 <文件名>` 与清单对应行比较。

## 发布版本（维护者）

1. 保持 `pyproject.toml` 与 `extension/manifest.json` 版本一致，合并到 main 并等待完整 CI 成功。
2. 打开 [Publish Release 工作流](https://github.com/yeshan333/tingsub/actions/workflows/release.yml)，选择 main，填写成功的 CI run ID 与对应 `vX.Y.Z` 标签。
3. 流程验证来源、版本和校验和，复用已测试的构建，将附件上传至草稿并核对上传后的大小和 SHA-256，再公开发布。不会重新编译，也不会覆盖已发布版本或移动已有标签。上传失败的同提交草稿可重试。

每个 Release 使用相同附件名，主页的 `releases/latest/download/...` 自动指向最新发布版本。发布为 Latest 表示最新可下载版本，不表示 Apple 公证或模型质量认证。日常 CI 仍只上传测试制品，不自动发布每个提交。

## 构建

### 下载 CI 预览版

打开 [CI 运行记录](https://github.com/yeshan333/tingsub/actions/workflows/ci.yml)，选择一次成功的 **main** 构建，在页面底部找到 **Artifacts**。下载 Actions 制品需要登录 GitHub，文件保留 **30 天**。它们是预览构建，不是 GitHub Release 或已通过 Apple 公证的正式版本。

| 制品 | 内容 |
| --- | --- |
| `TingSub-macos-arm64` | 带版本号的 `.dmg`、`.app.zip` 及各自的 SHA-256 文件 |
| `tingsub-extension` | `TingSub-extension-<version>.zip` 及其 SHA-256 文件 |

先解压 GitHub 下载的外层 ZIP。应用可打开 DMG 后拖入 Applications，也可解压里面的 `.app.zip`。最低 macOS 版本写在文件名中，只支持 Apple Silicon。App 包含 Python 运行环境和插件，首次使用时单独下载模型。通过桌面端的「打开插件文件夹」安装配套插件最方便。

单独使用插件制品时，把里面的 ZIP 解压到一个**固定目录**，在 `chrome://extensions` 开启开发者模式，加载包含 `manifest.json` 的文件夹。更新时保留目录、替换文件并重新加载已有插件，以保留 Chrome 插件 ID 和配对设置。该 ZIP 不是 CRX 或 Chrome 商店安装包。

在解压后的制品目录中校验文件：

```sh
shasum -a 256 -c *.sha256
```

每次 PR、main 推送和手动 CI 都检查并打包插件，Python 与浏览器检查通过后再构建 macOS 应用。可复用的 [Desktop bundle](https://github.com/yeshan333/tingsub/actions/workflows/desktop.yml) 工作流仍可单独手动触发，仅重建 App。整个 CI 不需要签名凭据，不下载模型，也不发布 Release。

### 本地构建

维护者需要 Apple Silicon Mac 和 uv，构建依赖由锁文件固定。

```sh
uv sync --frozen --extra desktop --group bundle --python 3.12
uv run --frozen --extra desktop --group bundle python scripts/build_desktop.py
```

输出为 `.local/bundle/TingSub.app`、`TingSub-<version>-macos-<minimum>-arm64.dmg`、对应的 `.app.zip` 和各自的 SHA-256 文件。应用版本读取 `pyproject.toml`，插件包版本读取 `extension/manifest.json`，两者应保持一致。PyInstaller 包含解释器、MLX 原生库、Metal 资源、推理依赖、桌面资源和 Chrome 插件。后台进程调用内置可执行文件，不依赖 PATH 或系统 Python。`--no-dmg` 只构建 App 和 App ZIP。

打包浏览器插件不需要 macOS 依赖：

```sh
python3 scripts/package_extension.py
```

脚本将可重复生成的版本化 ZIP 和校验文件写入 `dist/extension`，只包含明确列出的运行时文件及 MIT 许可证。新增插件资源时需同步更新打包脚本中的文件清单。

## 签名和公证

未配置身份时使用 ad-hoc 签名，可在本地执行，但**不是 Developer ID 签名或 Apple 公证**。下载后的制品可能触发 Gatekeeper 提示；不应关闭系统安全机制，也不能把它称为已公证版本。

维护者已有本机 Developer ID 凭据时，设置 `TINGSUB_CODESIGN_IDENTITY`。可选设置 `TINGSUB_NOTARY_PROFILE`，指向已配置的 `notarytool` 钥匙串配置；构建脚本会提交 DMG、等待公证通过并附加票据。凭据不进入仓库，发布前需在干净的 Mac 上验证。当前开发构建尚未经过公证。

## 验证与维护

CI 校验两个压缩包的 SHA-256 和 DMG 完整性，将 App ZIP 解压到源码目录外的临时位置，检查签名，并使用最小 PATH、隔离的数据目录启动内置 CLI 和原生 WebKit 自检。自检使用 `--no-inference`，覆盖打包后的界面与导航保护，不代表 GPU 推理或字幕质量验证。插件 ZIP 也会独立解压并由真实 Chromium 加载，检查弹窗和音频采集所需资源。缺少产物或检查失败会直接使 CI 失败，不会上传空制品。

```sh
/path/to/TingSub.app/Contents/MacOS/TingSub --self-test --data-dir /path/to/prepared-data
```

这项显式启用的检查打开真实 WebKit 窗口，验证外部导航被阻止，通过原生桥接启动真实模型服务，再停止服务。`--no-inference` 只检查页面与导航策略。验证独立运行时，应把 App 复制到源码目录外，从 `/tmp` 执行，清除开发环境变量并使用最小系统 PATH。命令行诊断入口为 `--worker --help`。

数据保存在 `~/Library/Application Support/TingSub`，替换 App 保留模型、配对和设置。新安装的 Chrome 插件导出到固定的 `extensions/extension` 路径；已有预览版的版本目录也会原地更新，保留 Chrome ID、本地配对和设置。替换 App 后点击「打开插件文件夹」更新文件，再在 Chrome 对已有插件点击「重新加载」，无需删除旧插件或另装一份。目前不支持自动更新。

卸载时退出 TingSub，移除 Applications 中的应用和 Chrome 插件。只有希望一并删除模型缓存、配对和设置时，才删除对应 Application Support 目录。源码运行的 `.local` 目录相互独立，不会自动迁移。

模型权重单独下载并遵循上游许可。第三方发行元数据及许可文件包含在 App 资源中，另见[模型与依赖说明](models.md)。构建成功不等于许可审核或准确率评测通过。

构建脚本读取所有打包的 Mach-O 依赖，以最高最低版本要求设置 `LSMinimumSystemVersion`，并写入 DMG 文件名。新系统可能选择要求更高的 MLX wheel，因此不能笼统宣称本机产物支持 macOS 14。若要分发低版本兼容包，应在目标最低系统构建并实测；仅 CI 构建通过不代表推理验证。
