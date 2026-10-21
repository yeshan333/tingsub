"""Build and start the MyGo host from a checkout or an installed app."""

import os
import platform
import subprocess
import sys
from pathlib import Path

from .runtime import bundled


def desktop_command(directory, *arguments):
    if bundled():
        binary = Path(sys.executable).with_name("TingSub")
        return [str(binary), "--data-dir", str(directory), *arguments]
    root = Path(__file__).resolve().parents[2]
    if not (root / "go.mod").is_file():
        raise SystemExit(
            "The desktop requires the TingSub app or a source checkout with Go 1.27.1+"
        )
    binary = root / ".local" / "bin" / "TingSub"
    binary.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Go's build cache makes repeated launches cheap and tracks embedded UI changes.
        subprocess.run(
            ["go", "build", "-trimpath", "-o", str(binary), "./cmd/tingsub"],
            cwd=root, check=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("Install Go 1.27.1+ to build the MyGo desktop") from exc
    return [
        str(binary), "--python", sys.executable, "--source-root", str(root),
        "--data-dir", str(directory), *arguments,
    ]


def launch(directory, *arguments):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("TingSub desktop requires an Apple Silicon Mac")
    command = desktop_command(Path(directory).resolve(), *arguments)
    os.execv(command[0], command)
