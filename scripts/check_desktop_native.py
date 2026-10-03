"""Opt-in native WebKit + real-model lifecycle check. Requires prepared local models.

Runs its own window and owned service. Does not automate the user's browser.
"""

import argparse
import json
import time
from pathlib import Path

from live_subs.desktop import launch, probe
from live_subs.server import token_at


def main():
    import webview

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(".local"))
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    if probe(token_at(directory))[0] != "stopped":
        raise SystemExit("Stop the existing local service before this check")
    original_start = webview.start
    result = {}

    def exercise():
        window = webview.windows[0]

        def wait_for(expression, seconds=90):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if window.evaluate_js(expression):
                    return
                time.sleep(0.2)
            raise AssertionError(f"Native UI timeout: {expression}")

        try:
            if not window.events.loaded.wait(20):
                raise AssertionError("Native page did not load")
            wait_for("!document.getElementById('serviceAction').disabled", 15)
            started = time.monotonic()
            window.evaluate_js("document.getElementById('serviceAction').click()")
            wait_for("document.getElementById('serviceDot').classList.contains('ready')")
            result["warmup_seconds"] = round(time.monotonic() - started, 2)
            assert probe(token_at(directory))[0] == "ready"
            window.evaluate_js("document.getElementById('serviceAction').click()")
            wait_for("document.getElementById('serviceDot').classList.contains('stopped')")
            assert probe(token_at(directory))[0] == "stopped"
            result["native_bridge_start_ready_stop"] = "passed"
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            window.destroy()

    def start(**kwargs):
        original_start(exercise, **kwargs)

    webview.start = start
    try:
        launch(directory)
    finally:
        webview.start = original_start
    print(json.dumps(result, indent=2))
    if "error" in result or not result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
