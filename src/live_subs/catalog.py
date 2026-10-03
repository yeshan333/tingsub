"""Curated multilingual MLX checkpoints. Weights keep their upstream licenses."""

DEFAULT_ASR = "mlx-community/whisper-large-v3-turbo-4bit"
DEFAULT_TRANSLATION = "mlx-community/Qwen2.5-3B-Instruct-4bit"
CATALOG = [
    {
        "kind": "asr",
        "repo": DEFAULT_ASR,
        "name": "Whisper Turbo · 4-bit",
        "description": {
            "zh-CN": "默认 · 兼顾识别质量和速度",
            "en": "Default · balanced recognition",
        },
        "license": "Apache-2.0 (conversion) / MIT (Whisper)",
        "license_url": "https://huggingface.co/mlx-community/whisper-large-v3-turbo-4bit",
    },
    {
        "kind": "asr",
        "repo": "mlx-community/whisper-small-mlx-4bit",
        "name": "Whisper Small · 4-bit",
        "description": {
            "zh-CN": "轻量 · 占用更低，复杂语音识别可能下降",
            "en": "Lightweight · lower memory, less accurate on difficult speech",
        },
        "license": "MIT",
        "license_url": "https://huggingface.co/openai/whisper-small",
    },
    {
        "kind": "translation",
        "repo": DEFAULT_TRANSLATION,
        "name": "Qwen 2.5 3B · 4-bit",
        "description": {
            "zh-CN": "默认 · 中日英字幕翻译",
            "en": "Default · Chinese/Japanese/English translation",
        },
        "license": "Qwen Research",
        "license_url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE",
    },
    {
        "kind": "translation",
        "repo": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        "name": "Qwen 2.5 1.5B · 4-bit",
        "description": {
            "zh-CN": "实验选项 · 更省内存，可能误译或补充原文没有的信息",
            "en": "Experimental · lower memory; may mistranslate or invent details",
        },
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE",
    },
]
