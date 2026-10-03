"""Explicit download sources and byte-based model preparation progress."""

import io
import threading
import time
from urllib.parse import urlsplit

from tqdm.auto import tqdm

SOURCES = {"official": "https://huggingface.co", "mirror": "https://hf-mirror.com"}


def validate_download(value):
    if value is None:
        return {"source": "official", "endpoint": SOURCES["official"]}
    if not isinstance(value, dict) or value.get("source") not in (*SOURCES, "custom"):
        raise ValueError("Choose a supported download source")
    source = value["source"]
    endpoint = SOURCES.get(source, value.get("endpoint", ""))
    if not isinstance(endpoint, str):
        raise ValueError("Download endpoint must be an HTTPS address")
    endpoint = endpoint.strip().rstrip("/")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an HTTPS endpoint without credentials, query or fragment")
    return {"source": source, "endpoint": endpoint}


class DownloadProgress:
    """Persist reconstructed file bytes, including resumed/cached bytes, at most 4Hz."""

    def __init__(self, emit, total=None, cached=0, interval=0.25):
        self.emit = emit
        self.total = total
        self.cached = cached
        self.interval = interval
        self.last = 0.0
        self.lock = threading.Lock()
        self.active = True
        self.counts = {}

    def report(self, count, *, bar=None, force=False):
        with self.lock:
            if not self.active:
                return
            # Keep finished bars and throttled updates in the snapshot total.
            # A delayed concurrent report must not overwrite a newer count.
            self.counts[bar] = max(self.counts.get(bar, 0), int(count))
            now = time.monotonic()
            if not force and now - self.last < self.interval:
                return
            self.last = now
            ready = max(0, self.cached + sum(self.counts.values()))
            if self.total is not None:
                ready = min(ready, self.total)
            self.emit({"bytes": ready, "total_bytes": self.total})

    def finish(self):
        with self.lock:
            self.active = False

    def progress_class(self):
        reporter = self

        class PreparationBar(tqdm):
            def __init__(self, *args, **kwargs):
                self.progress_key = object()
                name = kwargs.pop("name", "")
                self.tracked = kwargs.get("unit") == "B" and not name.endswith(".transfer")
                kwargs.update(disable=False, file=io.StringIO(), mininterval=0.25)
                super().__init__(*args, **kwargs)
                if self.tracked:
                    reporter.report(self.n, bar=self.progress_key)

            def update(self, n=1):
                result = super().update(n)
                if self.tracked:
                    reporter.report(self.n, bar=self.progress_key)
                return result

            def close(self):
                if getattr(self, "tracked", False) and hasattr(self, "n"):
                    reporter.report(self.n, bar=self.progress_key, force=True)
                super().close()

        return PreparationBar
