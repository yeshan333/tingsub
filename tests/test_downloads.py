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
