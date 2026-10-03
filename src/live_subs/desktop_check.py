"""Opt-in native WebKit + real-model lifecycle check. Requires prepared local models.

Runs its own window and owned service. Does not automate the user's browser.
"""

import argparse
import json
import threading
import time
from pathlib import Path

from live_subs import desktop_security
from live_subs.desktop import launch, probe
from live_subs.server import token_at


def main():
    import webview

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(".local"))
    parser.add_argument("--no-inference", action="store_true", help="Check native policy only")
    parser.add_argument("--asr", help="Exercise model selection and activation before startup")
    parser.add_argument(
        "--translation", help="Exercise model selection and activation before startup"
    )
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    if probe(token_at(directory))[0] != "stopped":
        raise SystemExit("Stop the existing local service before this check")
    original_start = webview.start
    result = {}
    rejected_navigation = threading.Event()
    original_policy = desktop_security.trusted_document

    def observed_policy(url, expected, main_frame):
        allowed = original_policy(url, expected, main_frame)
        if url == "http://127.0.0.1:9/untrusted" and not allowed:
            rejected_navigation.set()
        return allowed

    desktop_security.trusted_document = observed_policy

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
            entry = window.get_current_url()
            window.evaluate_js("location.href = 'http://127.0.0.1:9/untrusted'")
            assert rejected_navigation.wait(timeout=3), "Native navigation guard did not reject"
            assert window.get_current_url() == entry
            result["native_navigation_guard"] = "passed"
            if args.no_inference:
                return
            if args.asr or args.translation:
                window.evaluate_js("document.querySelector('[data-page=models]').click()")
                for kind, repo in (("asr", args.asr), ("translation", args.translation)):
                    if repo:
                        control = json.dumps(kind + "Model")
                        value = json.dumps(repo)
                        window.evaluate_js(
                            f"document.getElementById({control}).value = {value};"
                            f"document.getElementById({control}).dispatchEvent(new Event('change'))"
                        )
                assert not window.evaluate_js("document.getElementById('prepare').disabled")
                window.evaluate_js("document.getElementById('prepare').click()")
                wait_for("document.getElementById('serviceDot').classList.contains('preparing')")
                wait_for("document.getElementById('serviceDot').classList.contains('stopped')", 120)
                active = json.loads((directory / "models.json").read_text())
                for kind, repo in (("asr", args.asr), ("translation", args.translation)):
                    if repo:
                        assert active[kind]["repo"] == repo
                result["native_model_selection_and_activation"] = "passed"
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
        desktop_security.trusted_document = original_policy
    print(json.dumps(result, indent=2))
    if "error" in result or not result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
