"""Opt-in native WebKit + real-model lifecycle check. Requires prepared local models.

Runs its own window and owned service. Does not automate the user's browser.
"""

import argparse
import json
import threading
import time
from pathlib import Path
from urllib.parse import urljoin

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
    foreign_url = None

    def observed_policy(url, expected, main_frame):
        allowed = original_policy(url, expected, main_frame)
        if url == foreign_url and not allowed:
            rejected_navigation.set()
        return allowed

    desktop_security.trusted_document = observed_policy

    def exercise():
        nonlocal foreign_url
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
            # Use the working local server's port. Port 9 is browser-blocked and
            # can fail before WebKit calls our navigation-policy delegate.
            foreign_url = urljoin(entry, "__tingsub_untrusted_check__.html")
            window.evaluate_js(f"location.href = {json.dumps(foreign_url)}")
            assert rejected_navigation.wait(timeout=5), (
                f"Native navigation guard did not reject {foreign_url}; "
                f"current document: {window.get_current_url()}"
            )
            assert window.get_current_url() == entry
            result["native_navigation_guard"] = "passed"
            from PyObjCTools import AppHelper
            from webview.platforms.cocoa import BrowserView

            menu = window._tingsub_menubar
            assert menu.item is not None, "Native status item was not installed"

            def on_main(function):
                done = threading.Event()
                output = {}

                def run():
                    try:
                        output["value"] = function()
                    except Exception as exc:
                        output["error"] = exc
                    finally:
                        done.set()

                AppHelper.callAfter(run)
                assert done.wait(10), "Native menu action timed out"
                if "error" in output:
                    raise output["error"]
                return output.get("value")

            native = BrowserView.instances[window.uid].window
            on_main(lambda: native.performClose_(None))
            # Closing the window must keep both the app and status item alive.
            deadline = time.monotonic() + 5
            while on_main(native.isVisible) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert not on_main(native.isVisible)
            assert window in webview.windows and menu.item is not None
            on_main(lambda: menu.menu.performActionForItemAtIndex_(1))
            deadline = time.monotonic() + 5
            while not on_main(native.isVisible) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert on_main(native.isVisible), "Open menu action did not restore the window"
            window.evaluate_js(
                "document.getElementById('locale').value = 'en';"
                "document.getElementById('locale').dispatchEvent(new Event('change'))"
            )
            deadline = time.monotonic() + 6
            while on_main(lambda: str(menu.items["show"].title())) != "Open TingSub":
                assert time.monotonic() < deadline, "Menu locale did not follow desktop settings"
                time.sleep(0.2)
            result["native_menu_close_reopen_and_locale"] = "passed"
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
            menu = getattr(window, "_tingsub_menubar", None)
            if menu and menu.item is not None:
                from PyObjCTools import AppHelper

                AppHelper.callAfter(menu.request_quit)
            else:
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
