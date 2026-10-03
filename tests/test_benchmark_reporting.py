"""Reporting contracts only; these fixtures do not measure model performance."""

import runpy
from pathlib import Path

import pytest

BENCHMARK = runpy.run_path(str(Path(__file__).parents[1] / "scripts/benchmark_backends.py"))


def test_failed_utterance_remains_in_error_rate_and_counts_when_latency_has_only_successes():
    rows = [
        {
            "backend": "mlx",
            "language": "en",
            "counts": {"translated": 1},
            "edits": 0,
            "reference_units": 4,
            "metrics": [{"first_zh_ms": 500}],
        },
        {
            "backend": "mlx",
            "language": "en",
            "counts": {"errors": 1},
            "edits": 4,
            "reference_units": 4,
            "metrics": [],
        },
    ]
    result = BENCHMARK["summarize"](rows, "realtime")["mlx/en"]
    assert result["utterance_runs"] == 2
    assert result["counts"] == {"translated": 1, "errors": 1}
    assert result["error_rate"] == 0.5
    assert result["first_zh_ms"] == {"n": 1, "p50": 500, "p95": 500}


def test_missing_recognition_counts_every_reference_word_as_deleted():
    result = BENCHMARK["quality"]("", {"reference": "Bring your laptop", "language": "en"})
    assert result == {"edits": 3, "reference_units": 3}


def test_native_benchmark_rejects_remote_endpoints_before_sending_audio():
    with pytest.raises(ValueError, match="loopback"):
        BENCHMARK["NativeASR"]("https://example.com")
