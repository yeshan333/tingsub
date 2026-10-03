import argparse
import json
import os
import platform
import socket
from pathlib import Path

DEFAULT_ASR = "mlx-community/whisper-large-v3-turbo-4bit"
DEFAULT_TRANSLATION = "mlx-community/Qwen2.5-3B-Instruct-4bit"


def main():
    parser = argparse.ArgumentParser(description="TingSub · 听桥：完全本地的直播双语字幕")
    parser.add_argument("--data-dir", type=Path, default=Path(".local"))
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="首次联网下载模型；运行时不联网")
    prepare.add_argument("--asr", default=DEFAULT_ASR)
    prepare.add_argument("--translation", default=DEFAULT_TRANSLATION)
    prepare.add_argument("--force", action="store_true", help="忽略现有模型配置，重新解析并下载")
    serve = sub.add_parser("serve", help="预热本地模型并启动服务")
    serve.add_argument("--port", type=int, default=18765)
    sub.add_parser("pair", help="显示浏览器插件配对码")
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    if args.command == "prepare":
        from huggingface_hub import HfApi, snapshot_download

        api = HfApi()
        result = {}
        existing_file = directory / "models.json"
        existing = json.loads(existing_file.read_text()) if existing_file.exists() else {}
        for kind, repo in [("asr", args.asr), ("translation", args.translation)]:
            previous = existing.get(kind, {})
            previous_path = Path(previous.get("path", "/nonexistent"))
            if (
                not args.force
                and previous.get("repo") == repo
                and (previous_path / "config.json").is_file()
            ):
                weights = list(previous_path.glob("*.safetensors")) + list(
                    previous_path.glob("*.npz")
                )
                if weights:
                    result[kind] = previous
                    print(f"复用已下载的 {kind}: {repo} @ {previous['revision']}", flush=True)
                    continue
            revision = api.model_info(repo).sha
            print(f"下载 {kind}: {repo} @ {revision}", flush=True)
            path = snapshot_download(
                repo,
                revision=revision,
                allow_patterns=["*.json", "*.safetensors", "*.npz", "*.txt", "*.model", "*.jinja"],
            )
            result[kind] = {"repo": repo, "revision": revision, "path": path}
        temporary = directory / "models.json.tmp"
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        temporary.replace(directory / "models.json")
        print("模型已固定到具体版本；后续运行只读取本地文件。")
    else:
        from .server import token_at

        if args.command == "pair":
            print(token_at(directory))
            return
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            parser.error("此版本的推理后端要求 Apple Silicon Mac")
        if not (directory / "models.json").exists():
            parser.error("请先执行 uv run tingsub prepare 下载本地模型")
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", args.port))
            except OSError:
                parser.error(f"127.0.0.1:{args.port} 已被占用，请先确认服务是否已经启动")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import uvicorn

        from .server import create_app

        print("正在加载并预热模型，首次可能需要几十秒。配对码用 tingsub pair 查看。", flush=True)
        uvicorn.run(
            create_app(directory),
            host="127.0.0.1",
            port=args.port,
            ws_max_size=4096,
            ws_max_queue=4,
            access_log=False,
        )


if __name__ == "__main__":
    main()
