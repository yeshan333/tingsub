"""Private newline-delimited JSON RPC over the MyGo child's stdin/stdout.

No listening socket, arbitrary attribute dispatch, or user-provided executable.
EOF (including a crashed host) closes only this controller's owned work.
"""

import contextlib
import json
import signal
import sys

from .desktop import DesktopAPI, DesktopController
from .menubar import WORDS, menu_state

MAX_REQUEST = 64 * 1024


def methods_for(controller):
    api = DesktopAPI(controller)

    def menu_snapshot():
        locale = api.get_interface()["locale"]
        return {**menu_state(controller.service_status(), locale), "words": WORDS[locale]}

    def service_action():
        status = controller.service_status()
        if status["owned"] and status["state"] != "stopping":
            return controller.stop_service()
        if status["state"] in {"stopped", "error"}:
            return controller.start_service()
        return {"ok": False}

    return {
        "snapshot": api.snapshot,
        "start_service": api.start_service,
        "stop_service": api.stop_service,
        "prepare_models": api.prepare_models,
        "save_preferences": api.save_preferences,
        "get_interface": api.get_interface,
        "save_interface": api.save_interface,
        "copy_pairing": api.copy_pairing,
        "open_resource": api.open_resource,
        "menu_snapshot": menu_snapshot,
        "service_action": service_action,
    }


def dispatch(request, methods):
    if not isinstance(request, dict) or set(request) != {"method", "params"}:
        raise ValueError("Expected method and params")
    name, params = request["method"], request["params"]
    if not isinstance(name, str) or name not in methods:
        raise ValueError("Unknown desktop method")
    if not isinstance(params, list):
        raise ValueError("Desktop params must be an array")
    return methods[name](*params)


def run(controller, source, output):
    methods = methods_for(controller)
    try:
        while line := source.readline(MAX_REQUEST + 1):
            if len(line) > MAX_REQUEST:
                raise ValueError("Desktop request is too large")
            try:
                # Keep dependency output away from the protocol stream.
                with contextlib.redirect_stdout(sys.stderr):
                    value = dispatch(json.loads(line), methods)
                response = {"result": value}
            except Exception as exc:
                response = {"error": str(exc).replace(controller._token, "[redacted]")}
            output.write(json.dumps(response, ensure_ascii=False) + "\n")
            output.flush()
    finally:
        controller.close()


def serve(directory):
    def terminate(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    run(DesktopController(directory), sys.stdin, sys.stdout)
