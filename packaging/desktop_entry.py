"""Bundled Python sidecar: CLI, private desktop RPC, and inference workers."""

import multiprocessing
import sys


def run():
    multiprocessing.freeze_support()
    if sys.argv[1:2] == ["--worker"]:
        del sys.argv[1]
    from live_subs.cli import main

    main()


if __name__ == "__main__":
    run()
