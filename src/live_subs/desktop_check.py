"""Opt-in native MyGo/WebKit and real-model lifecycle check."""

import argparse
from pathlib import Path

from .desktop import launch, probe
from .server import token_at


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(".local"))
    parser.add_argument("--no-inference", action="store_true")
    parser.add_argument("--asr")
    parser.add_argument("--translation")
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    if probe(token_at(directory))[0] != "stopped":
        raise SystemExit("Stop the existing local service before this check")
    arguments = ["--self-test"]
    if args.no_inference:
        arguments.append("--no-inference")
    for name in ("asr", "translation"):
        if value := getattr(args, name):
            arguments.extend([f"--{name}", value])
    launch(directory, *arguments)


if __name__ == "__main__":
    main()
