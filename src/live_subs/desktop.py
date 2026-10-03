"""Small native WebKit host. Inference remains in an owned, isolated subprocess."""

import http.client
import json
import os
import platform
import socket
import subprocess
import threading
import webbrowser
from pathlib import Path

from .catalog import DEFAULT_ASR, DEFAULT_TRANSLATION
from .downloads import validate_download
from .model_manager import (
    catalog_at,
    read_config,
    selection_at,
    snapshot_status,
    validate_selection,
)
from .operation import acquire_operation
from .preferences import read_preferences, update_preferences
from .runtime import install_extension, worker_command
from .server import token_at

LINKS = {
    "guide": "https://github.com/yeshan333/tingsub/blob/main/docs/zh-CN/installation.md",
    "github": "https://github.com/yeshan333/tingsub",
    "licenses": "https://github.com/yeshan333/tingsub/blob/main/docs/en/models.md",
    "license": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE",
}


def probe(token):
    # Fixed loopback destination: no environment proxy and no followed redirects.
    def get(path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", 18765, timeout=0.4)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError("Unexpected response")
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("Response too large")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError("Unexpected response")
            return value
        finally:
            connection.close()

    try:
        health = get("/health")
        if health.get("service") != "tingqiao" or health.get("protocol") != 1:
            return "conflict", False
        get("/preferences", {"Authorization": f"Bearer {token}"})
        return "ready", bool(health.get("busy"))
    except (OSError, ValueError, http.client.HTTPException):
        with socket.socket() as connection:
            connection.settimeout(0.2)
            occupied = connection.connect_ex(("127.0.0.1", 18765)) == 0
        return ("conflict" if occupied else "stopped"), False


class DesktopController:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._token = token_at(self.directory)
        self._lock = threading.RLock()
        self._process = None
        self._operation_lock = None
        self._job = None
        self._closing = False
        self._stopping = False
        self._error = ""
        self._log = self.directory / "desktop.log"

    def _models(self):
        path = self.directory / "models.json"
        try:
            config = json.loads(path.read_text()) if path.exists() else {}
        except (OSError, ValueError):
            config = {}
        result = []
        for kind, repo in (("asr", DEFAULT_ASR), ("translation", DEFAULT_TRANSLATION)):
            item = config.get(kind, {})
            ready, size = snapshot_status(item)
            result.append(
                {
                    "kind": kind,
                    "repo": item.get("repo", repo),
                    "ready": ready,
                    "bytes": size,
                }
            )
        return result

    def _release_operation(self):
        if self._operation_lock is not None:
            self._operation_lock.close()
            self._operation_lock = None

    def _acquire_operation(self):
        return acquire_operation(self.directory)

    def _reap(self):
        if self._process is not None and self._process.poll() is not None:
            code = self._process.returncode
            if code and not self._stopping:
                self._error = f"{self._job} exited ({code})"
            self._process = None
            self._job = None
            self._release_operation()

    def snapshot(self):
        with self._lock:
            self._reap()
            state, busy = probe(self._token)
            owned = self._process is not None
            if self._stopping:
                state = "stopping"
            elif self._job == "prepare":
                state = "preparing"
            elif self._job == "serve" and state != "ready":
                state = "starting"
            elif self._error and state == "stopped":
                state = "error"
            logs = ""
            if self._log.exists():
                with self._log.open("rb") as stream:
                    stream.seek(max(0, self._log.stat().st_size - 6000))
                    logs = stream.read().decode("utf-8", errors="replace")
            return {
                "state": state,
                "busy": busy,
                "owned": owned,
                "models": self._models(),
                "catalog": catalog_at(self.directory),
                "selection": selection_at(self.directory),
                "model_cache": str(self.directory / "model-cache"),
                "preparation": read_config(self.directory / "preparation.json"),
                "download": validate_download(
                    read_config(self.directory / "download.json") or None
                ),
                "preferences": read_preferences(self.directory),
                "error": self._error,
                "logs": logs.replace(self._token, "[redacted]"),
            }

    def _spawn(self, job, arguments=()):
        with self._lock:
            self._reap()
            if self._closing or self._stopping or self._process is not None:
                raise RuntimeError("Another operation is in progress")
            self._operation_lock = self._acquire_operation()
            try:
                state, _ = probe(self._token)
                if state != "stopped":
                    raise RuntimeError(
                        "Port 18765 is already in use; stop the existing service first"
                    )
                if job == "serve" and not all(item["ready"] for item in self._models()):
                    raise RuntimeError("Download the local models first")
                with self._log.open("wb") as output:
                    self._process = subprocess.Popen(
                        worker_command(self.directory, job, *arguments),
                        env={
                            **os.environ,
                            "TINGSUB_OPERATION_FD": str(self._operation_lock.fileno()),
                        },
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        # The child retains ownership if the desktop unexpectedly exits.
                        pass_fds=(self._operation_lock.fileno(),),
                    )
                self._job, self._error = job, ""
            except Exception:
                self._release_operation()
                raise
        return {"ok": True}

    def start_service(self):
        return self._spawn("serve")

    def prepare_models(self, selection=None, download=None):
        source = validate_download(
            download or read_config(self.directory / "download.json") or None
        )
        selected = validate_selection(self.directory, selection or selection_at(self.directory))
        return self._spawn(
            "prepare",
            (
                "--asr",
                selected["asr"],
                "--translation",
                selected["translation"],
                "--validate",
                "--download-source",
                source["source"],
                "--endpoint",
                source["endpoint"],
            ),
        )

    def _terminate(self, process):
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
                    self._job = None
                    self._release_operation()
                self._stopping = False

    def stop_service(self):
        with self._lock:
            if self._process is not None and not self._stopping:
                self._stopping = True
                threading.Thread(target=self._terminate, args=(self._process,), daemon=True).start()
        return {"ok": True}

    def close(self):
        with self._lock:
            self._closing = True
            process = self._process
            stopping = self._stopping
            if process is not None:
                self._stopping = True
        if process is not None and not stopping:
            self._terminate(process)
        elif process is not None:
            process.wait(timeout=15)


class DesktopAPI:
    """Only these explicit capabilities are exposed to the bundled page."""

    def __init__(self, controller):
        self._controller = controller

    def snapshot(self):
        return self._controller.snapshot()

    def start_service(self):
        return self._controller.start_service()

    def stop_service(self):
        return self._controller.stop_service()

    def prepare_models(self, selection=None, download=None):
        return self._controller.prepare_models(selection, download)

    def save_preferences(self, patch):
        return update_preferences(self._controller.directory, patch)

    def get_interface(self):
        path = self._controller.directory / "interface.json"
        try:
            value = json.loads(path.read_text())
            if value.get("locale") in ("zh-CN", "en") and value.get("theme") in (
                "dark",
                "light",
                "system",
            ):
                return {"locale": value["locale"], "theme": value["theme"]}
        except (OSError, ValueError, AttributeError):
            pass
        return {"locale": "zh-CN", "theme": "dark"}

    def save_interface(self, value):
        if not isinstance(value, dict) or value.get("locale") not in ("zh-CN", "en"):
            raise ValueError("Unsupported interface language")
        if value.get("theme") not in ("dark", "light", "system"):
            raise ValueError("Unsupported appearance")
        with self._controller._lock:
            path = self._controller.directory / "interface.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"locale": value["locale"], "theme": value["theme"]}))
            temporary.replace(path)
        return {"ok": True}

    def copy_pairing(self):
        subprocess.run(
            ["/usr/bin/pbcopy"], input=self._controller._token.encode(), check=True, timeout=3
        )
        return {"ok": True}

    def open_resource(self, name):
        if name == "extension":
            extension = install_extension(self._controller.directory)
            if not (extension / "manifest.json").is_file():
                raise RuntimeError("Extension folder not found. Download it from the repository.")
            subprocess.run(["/usr/bin/open", str(extension)], check=True, timeout=3)
        elif name == "models":
            folder = self._controller.directory / "model-cache"
            folder.mkdir(parents=True, exist_ok=True)
            subprocess.run(["/usr/bin/open", str(folder)], check=True, timeout=3)
        elif name == "logs":
            log = self._controller._log
            arguments = ["/usr/bin/open", "-R", str(log)] if log.is_file() else [
                "/usr/bin/open", str(self._controller.directory)
            ]
            subprocess.run(arguments, check=True, timeout=3)
        elif name == "chrome":
            subprocess.run(
                ["/usr/bin/open", "-a", "Google Chrome", "chrome://extensions"],
                check=True,
                timeout=3,
            )
        elif name in LINKS:
            webbrowser.open(LINKS[name])
        else:
            raise ValueError("Unknown resource")
        return {"ok": True}


def launch(directory):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("TingSub desktop requires an Apple Silicon Mac")
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("Install desktop support: uv sync --extra desktop") from exc
    controller = DesktopController(directory)
    window = webview.create_window(
        "TingSub",
        str(Path(__file__).with_name("desktop_ui") / "index.html"),
        width=1060,
        height=780,
        min_size=(880, 660),
        background_color="#151719",
        text_select=False,
    )
    api = DesktopAPI(controller)

    def secure_window():
        from .desktop_security import install_cocoa_guards

        # Event handlers swallow ordinary exceptions. Expose capabilities only after
        # successful policy installation, so any failure leaves an inert window.
        install_cocoa_guards(window)
        window.expose(
            api.snapshot,
            api.start_service,
            api.stop_service,
            api.prepare_models,
            api.save_preferences,
            api.get_interface,
            api.save_interface,
            api.copy_pairing,
            api.open_resource,
        )

    window.events.before_show += secure_window
    window.events.closed += controller.close
    try:
        webview.start(gui="cocoa", debug=False)
    finally:
        controller.close()
