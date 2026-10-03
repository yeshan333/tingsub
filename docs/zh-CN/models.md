[English](../en/models.md) · [简体中文](../zh-CN/models.md) · [Index](README.md)

# 模型与第三方许可

TingSub 的 [MIT 许可](../../LICENSE)只覆盖项目自身源码，不重新授权模型权重、数据集、上游代码或依赖。仓库及扩展压缩包均不包含模型权重。

## 默认模型

| 用途 | 模型 | 上游许可信息 |
| --- | --- | --- |
| 语音识别 | [mlx-community/whisper-large-v3-turbo-4bit](https://huggingface.co/mlx-community/whisper-large-v3-turbo-4bit) | 转换后模型卡声明 Apache-2.0。原始 [OpenAI Whisper 仓库](https://github.com/openai/whisper)的代码与权重采用 MIT；请保留所用具体制品对应的许可说明。 |
| 翻译 | [mlx-community/Qwen2.5-3B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen2.5-3B-Instruct-4bit) | 模型卡声明 `qwen-research`，链接到 [Qwen2.5-3B-Instruct 许可](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE)。这是包含非商业条件和单独商业授权流程的研究许可，不是 Apache-2.0 或 MIT。 |

默认技术栈在本地运行，但并非所有权重都采用宽松开源许可。请按实际用途阅读条款。Qwen 不同参数规模可能采用不同许可，不能由系列名称推断 3B 模型的许可。替换默认翻译模型前，需要验证兼容性、质量与性能。

## 版本与下载

`tingsub prepare` 解析所选仓库的当前提交，下载快照，并把 `repo`、`revision`、本地绝对 `path` 写入 `.local/models.json`。已完成的相同选择会复用，`--force` 才主动重新解析。因此模型版本是**每次安装后固定**，并非 CLI 全局写死同一版本。

初始本机验证使用：

| 模型 | 提交 |
| --- | --- |
| Whisper Turbo 4-bit | `0f058d38170d183f9fdee07908f5b515d91793a8` |
| Qwen2.5-3B-Instruct 4-bit | `4f83f8f146fdf28b512a06562b671d7af4fab457` |

性能对比请记录本机实际版本，上游默认版本可能前进。`.local/models.json` 包含机器路径，请勿公开。启动服务时启用 Hugging Face／Transformers 离线模式，要求本地权重完整。Whisper 文件名适配只创建本地链接，不修改上游快照。

实验时可以用 `tingsub prepare --asr REPOSITORY --translation REPOSITORY` 选择其他仓库，但不保证通用兼容。下载前先核对许可，并执行真实模型检查。不要仅为了改善合成语音延迟而牺牲准确率。

## 依赖与致谢

Python 与 JavaScript 依赖分别采用各自许可，具体解析版本和下载来源记录在 `uv.lock` 与 `package-lock.json`。主要上游项目：

- [MLX](https://github.com/ml-explore/mlx)、[MLX LM](https://github.com/ml-explore/mlx-lm)、[MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)。
- [OpenAI Whisper](https://github.com/openai/whisper)、[Qwen2.5](https://github.com/QwenLM/Qwen2.5)。
- [py-webrtcvad／内含 WebRTC 声明](https://github.com/wiseman/py-webrtcvad/blob/master/LICENSE)、[webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels)。
- [FastAPI](https://github.com/fastapi/fastapi)、[Uvicorn](https://github.com/encode/uvicorn)、[NumPy](https://github.com/numpy/numpy)、[Hugging Face Hub](https://github.com/huggingface/huggingface_hub)。
- [Playwright](https://github.com/microsoft/playwright)，仅用于开发测试。

此列表用于致谢和索引，不能替代每个实际依赖版本的许可。重新分发依赖或模型制品时，请附带对应许可和声明。源码仓库及 Chrome 扩展没有捆绑这些 Python 库或模型权重。
