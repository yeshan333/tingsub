"""Download progress measures bytes; it never estimates model loading progress."""

import pytest

from live_subs.downloads import DownloadProgress, validate_download


def test_community_source_uses_explicit_mirror_and_custom_source_requires_https():
    assert validate_download({"source": "mirror"})["endpoint"] == "https://hf-mirror.com"
    assert (
        validate_download({"source": "custom", "endpoint": " https://models.example/ "})["endpoint"]
        == "https://models.example"
    )
    for endpoint in (
        "http://models.example",
        "https://user:secret@models.example",
        "https://models.example?token=secret",
        "file:///tmp/models",
    ):
        with pytest.raises(ValueError):
            validate_download({"source": "custom", "endpoint": endpoint})


def test_progress_includes_cached_bytes_without_double_counting_transfer_and_stops_after_download():
    events = []
    progress = DownloadProgress(events.append, total=1000, cached=100, interval=0)
    bar = progress.progress_class()
    transfer = bar(total=900, unit="B", name="huggingface_hub.snapshot_download.transfer")
    reconstructed = bar(total=900, unit="B", name="huggingface_hub.snapshot_download")
    transfer.update(400)
    reconstructed.update(200)
    assert events[-1] == {"bytes": 300, "total_bytes": 1000}
    reconstructed.update(700)
    assert events[-1] == {"bytes": 1000, "total_bytes": 1000}
    progress.finish()
    count = len(events)
    transfer.close()
    reconstructed.close()
    assert len(events) == count, (
        "late bar cleanup must not replace model validation with download status"
    )


def test_unknown_download_size_reports_bytes_without_inventing_a_percentage():
    events = []
    progress = DownloadProgress(events.append)
    progress.report(123, force=True)
    assert events == [{"bytes": 123, "total_bytes": None}]


def test_concurrent_file_progress_keeps_completed_files_and_counts_resumed_bytes_once():
    events = []
    progress = DownloadProgress(events.append, total=1000, cached=100, interval=0)
    bar = progress.progress_class()
    first = bar(total=500, initial=100, unit="B")
    second = bar(total=400, unit="B")
    try:
        first.update(200)
        second.update(150)
        assert events[-1]["bytes"] == 550
        first.update(200)
        first.close()
        second.update(250)
        second.close()
        first.close()
        assert events[-1] == {"bytes": 1000, "total_bytes": 1000}
        assert [event["bytes"] for event in events] == sorted(event["bytes"] for event in events)
    finally:
        progress.finish()
        first.close()
        second.close()


def test_throttled_and_delayed_file_updates_cannot_lose_progress_or_move_it_backwards(monkeypatch):
    events = []
    monkeypatch.setattr("live_subs.downloads.time.monotonic", lambda: 1)
    progress = DownloadProgress(events.append, total=1000, interval=10)
    progress.report(300, bar="first", force=True)
    progress.report(200, bar="second")
    progress.report(100, bar="first")
    assert len(events) == 1
    progress.report(250, bar="second", force=True)
    assert events[-1]["bytes"] == 550


def test_hub_snapshot_aggregates_parallel_shards_without_counting_network_bytes_twice(
    tmp_path, monkeypatch
):
    import importlib
    from threading import Barrier

    from huggingface_hub import RepoFile, snapshot_download

    hub = importlib.import_module("huggingface_hub._snapshot_download")
    files = {"cached.json": 100, "first.safetensors": 500, "second.safetensors": 400}
    monkeypatch.setattr(
        hub.HfApi, "list_repo_tree",
        lambda *args, **kwargs: [
            RepoFile(path=name, size=size, oid="b" * 40) for name, size in files.items()
        ],
    )
    barrier = Barrier(2)

    def fetch(repo, *, filename, tqdm_class, **kwargs):
        if filename == "cached.json":
            return str(tmp_path / filename)
        size = files[filename]
        with tqdm_class(total=size, initial=0, unit="B") as bar:
            barrier.wait(timeout=5)
            bar.update(100)
            bar.update_transfer(size)
            barrier.wait(timeout=5)
            bar.update(size - 100)
        return str(tmp_path / filename)

    monkeypatch.setattr(hub, "hf_hub_download", fetch)
    events = []
    progress = DownloadProgress(events.append, total=1000, cached=100, interval=0)
    try:
        snapshot_download(
            "example/model", revision="a" * 40, cache_dir=tmp_path,
            token=False, max_workers=3, tqdm_class=progress.progress_class(),
        )
        assert events[-1] == {"bytes": 1000, "total_bytes": 1000}
        assert [event["bytes"] for event in events] == sorted(event["bytes"] for event in events)
    finally:
        progress.finish()
