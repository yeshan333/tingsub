[English](../en/models.md) · [简体中文](../zh-CN/models.md) · [Index](README.md)

# Models and third-party licenses

TingSub's [MIT license](../../LICENSE) applies to its own source code. It does **not** relicense model weights, datasets, upstream code or dependencies. No model weights are committed to this repository or included in the extension archive.

## Default checkpoints

| Purpose | Checkpoint | Upstream license information |
| --- | --- | --- |
| Speech recognition | [mlx-community/whisper-large-v3-turbo-4bit](https://huggingface.co/mlx-community/whisper-large-v3-turbo-4bit) | The converted checkpoint's card declares Apache-2.0. The original [OpenAI Whisper repository](https://github.com/openai/whisper) distributes its code/weights under MIT; retain the notices applicable to the exact artifact you use. |
| Translation | [mlx-community/Qwen2.5-3B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen2.5-3B-Instruct-4bit) | The card declares `qwen-research`, linking to the [Qwen2.5-3B-Instruct license](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE). This is a research license with non-commercial conditions and a separate commercial licensing process; it is not Apache-2.0 or MIT. |

The default stack is local, but its weights do not all have a permissive open-source license. Read the actual terms for your intended usage. Other Qwen sizes can have different licenses; do not infer this 3B checkpoint's terms from the family name. An alternative translation model requires compatibility, quality and performance validation before it can replace this default.

## Revisions and downloads

`tingsub prepare` resolves the selected repository to its current commit, downloads a snapshot, and records `repo`, `revision` and absolute local `path` in `.local/models.json`. A completed prior selection is reused. `--force` intentionally resolves it again. Thus versions are pinned **per installation**, not globally hardcoded in the CLI.

Initial local validation used:

| Model | Revision |
| --- | --- |
| Whisper Turbo 4-bit | `0f058d38170d183f9fdee07908f5b515d91793a8` |
| Qwen2.5-3B-Instruct 4-bit | `4f83f8f146fdf28b512a06562b671d7af4fab457` |

Record the revision from your own installation for comparisons; upstream defaults may move. Keep `.local/models.json` private because it includes machine-specific paths. Serving enables Hugging Face / Transformers offline mode and requires complete local weights. The Whisper filename adapter creates local links without modifying upstream snapshots.

For experiments, `tingsub prepare --asr REPOSITORY --translation REPOSITORY` selects other repositories. This is not a generic model compatibility guarantee. Review their licenses before downloading, and run the real-model checks. Do not change weights merely to improve a synthetic latency number at the expense of accuracy.

## Dependencies and notices

Python and JavaScript packages are separately licensed; exact resolved versions and download sources are in `uv.lock` and `package-lock.json`. Key upstream projects:

- [MLX](https://github.com/ml-explore/mlx), [MLX LM](https://github.com/ml-explore/mlx-lm), [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
- [OpenAI Whisper](https://github.com/openai/whisper), [Qwen2.5](https://github.com/QwenLM/Qwen2.5).
- [py-webrtcvad / bundled WebRTC notices](https://github.com/wiseman/py-webrtcvad/blob/master/LICENSE), [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels).
- [FastAPI](https://github.com/fastapi/fastapi), [Uvicorn](https://github.com/encode/uvicorn), [NumPy](https://github.com/numpy/numpy), [Hugging Face Hub](https://github.com/huggingface/huggingface_hub).
- [Playwright](https://github.com/microsoft/playwright), used for development tests only.

This list is attribution and orientation, not a substitute for every resolved package's license. If you redistribute dependencies or model artifacts, include their applicable licenses and notices. The source checkout and Chrome extension do not bundle those Python libraries or model weights.

## Models selectable in the desktop app

| Role | Checkpoint | License | Guidance |
|---|---|---|---|
| Speech | `mlx-community/whisper-large-v3-turbo-4bit` | Apache-2.0 (conversion) / MIT (Whisper) | Default |
| Speech | `mlx-community/whisper-small-mlx-4bit` | MIT (upstream Whisper) | Lower memory; recognition tradeoff |
| Translation | `mlx-community/Qwen2.5-3B-Instruct-4bit` | Qwen Research License | Default |
| Translation | `mlx-community/Qwen2.5-1.5B-Instruct-4bit` | Apache-2.0 | Experimental; lower memory, weaker fidelity |

The 1.5B option passed 19/28 authored translation checks on 2026-10-04 (M4 Pro), with failures including invented time-of-day details and missed content. These checks are not a general quality benchmark; keep 3B as the default. Small + 1.5B successfully loads and produces captions, but compatibility does not imply equal translation quality. Model switching downloads a pinned snapshot and validates before activation; cached versions remain fixed until an explicit CLI `prepare --force` refresh.

Upstream licenses: [Whisper](https://github.com/openai/whisper/blob/main/LICENSE), [Qwen 1.5B](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE), [Qwen 3B](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE). PyInstaller's bootloader uses a GPL exception permitting bundled applications; dependencies keep their respective licenses.
