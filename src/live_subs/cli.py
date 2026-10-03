import argparse
import os
import platform
import socket
from pathlib import Path

from .catalog import DEFAULT_ASR, DEFAULT_TRANSLATION  # noqa: F401
from .runtime import default_data_directory


def main():
    parser = argparse.ArgumentParser(description="TingSub · 听桥：完全本地的直播双语字幕")
    parser.add_argument("--data-dir", type=Path, default=default_data_directory())
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="首次联网下载模型；运行时不联网")
    prepare.add_argument(
        "--download-source", choices=("official", "mirror", "custom"), default="official"
    )
    prepare.add_argument(
        "--endpoint", help="HTTPS Hugging Face-compatible endpoint for custom source"
    )
    prepare.add_argument("--asr")
    prepare.add_argument("--translation")
    prepare.add_argument("--validate", action="store_true", help="实际加载校验后才启用新模型")
    prepare.add_argument("--force", action="store_true", help="忽略现有模型配置，重新解析并下载")
    serve = sub.add_parser("serve", help="预热本地模型并启动服务")
    serve.add_argument("--port", type=int, default=18765)
    sub.add_parser("gui", help="打开 TingSub 桌面窗口")
    sub.add_parser("pair", help="显示浏览器插件配对码")
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    if args.command == "gui":
        from .desktop import launch

        launch(directory)
        return

    if args.command == "pair":
        from .server import token_at

        print(token_at(directory))
        return
    from .operation import acquire_operation

    with acquire_operation(directory, os.environ.pop("TINGSUB_OPERATION_FD", None)):
        run_operation(args, directory, parser)


def run_operation(args, directory, parser):
    if args.command == "prepare":
        from .model_manager import prepare_models

        prepare_models(
            directory,
            args.asr,
            args.translation,
            force=args.force,
            validate=args.validate,
            download={"source": args.download_source, "endpoint": args.endpoint},
        )
    else:
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
