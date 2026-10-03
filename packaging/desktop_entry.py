"""Standalone entry point; --worker runs inference/downloads without another window."""

import multiprocessing
import os
import sys


def run():
    multiprocessing.freeze_support()
    for name, fd in (("stdout", 1), ("stderr", 2)):
        if getattr(sys, name) is None:
            setattr(sys, name, os.fdopen(os.dup(fd), "w", buffering=1))
    if sys.argv[1:2] == ["--self-test"]:
        sys.argv.pop(1)
        from live_subs.desktop_check import main
        main()
        return
    from live_subs.cli import main

    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        del sys.argv[1]
    elif len(sys.argv) == 1:
        sys.argv.append("gui")
    main()


if __name__ == "__main__":
    run()
