[English](../en/distribution.md) · [简体中文](../zh-CN/distribution.md) · [索引](README.md)

# macOS 独立应用分发

用户打开 DMG 并将 TingSub 拖入 Applications 即可，不需要安装 Python、uv、Homebrew 或下载源码。首次使用在界面中下载模型、按引导配对 Chrome，见[桌面指南](desktop.md)。App 在 DMG 压缩前约 1 GB；模型缓存另计，不随安装包附带。

## 构建

维护者需要 Apple Silicon Mac 和 uv，构建依赖由锁文件固定。

```sh
uv sync --frozen --extra desktop --group bundle --python 3.12
uv run --frozen --extra desktop --group bundle python scripts/build_desktop.py
```

输出为 `.local/bundle/TingSub.app`、`TingSub-0.1.0-macos-<minimum>-arm64.dmg` 和 SHA-256 文件。PyInstaller 包含解释器、MLX 原生库、Metal 资源、推理依赖、桌面资源和 Chrome 插件。后台进程调用内置可执行文件，不依赖 PATH 或系统 Python。GitHub Actions 的 `Desktop bundle` 工作流可手动触发，只生成尚未签名公证的分发制品，不发布 GitHub Release，也不下载模型。

## 签名和公证

未配置身份时使用 ad-hoc 签名，可在本地执行，但**不是 Developer ID 签名或 Apple 公证**。下载后的制品可能触发 Gatekeeper 提示；不应关闭系统安全机制，也不能把它称为已公证版本。

维护者已有本机 Developer ID 凭据时，设置 `TINGSUB_CODESIGN_IDENTITY`。可选设置 `TINGSUB_NOTARY_PROFILE`，指向已配置的 `notarytool` 钥匙串配置；构建脚本会提交 DMG、等待公证通过并附加票据。凭据不进入仓库，发布前需在干净的 Mac 上验证。当前开发构建尚未经过公证。

## 验证与维护

```sh
/path/to/TingSub.app/Contents/MacOS/TingSub --self-test --data-dir /path/to/prepared-data
```

这项显式启用的检查打开真实 WebKit 窗口，验证外部导航被阻止，通过原生桥接启动真实模型服务，再停止服务。`--no-inference` 只检查页面与导航策略。验证独立运行时，应把 App 复制到源码目录外，从 `/tmp` 执行，清除开发环境变量并使用最小系统 PATH。命令行诊断入口为 `--worker --help`。

数据保存在 `~/Library/Application Support/TingSub`，替换 App 保留模型、配对和设置。Chrome 插件导出到按内容区分的版本目录，替换 App 不会破坏已加载插件。更新后加载新导出的插件，并手动移除浏览器内的旧版本。目前不支持自动更新。

卸载时退出 TingSub，移除 Applications 中的应用和 Chrome 插件。只有希望一并删除模型缓存、配对和设置时，才删除对应 Application Support 目录。源码运行的 `.local` 目录相互独立，不会自动迁移。

模型权重单独下载并遵循上游许可。第三方发行元数据及许可文件包含在 App 资源中，另见[模型与依赖说明](models.md)。构建成功不等于许可审核或准确率评测通过。

构建脚本读取所有打包的 Mach-O 依赖，以最高最低版本要求设置 `LSMinimumSystemVersion`，并写入 DMG 文件名。新系统可能选择要求更高的 MLX wheel，因此不能笼统宣称本机产物支持 macOS 14。若要分发低版本兼容包，应在目标最低系统构建并实测；仅 CI 构建通过不代表推理验证。
