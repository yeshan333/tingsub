"""Accounting contracts only; no model performance is simulated here."""

import runpy
from pathlib import Path


def test_translation_failure_stays_in_attempts_without_becoming_a_fast_success(monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    summarize = runpy.run_path(str(scripts / "benchmark_native_routes.py"))["translation_summary"]
    result = summarize(
        [
            {"backend": "swift", "language": "ja", "success": True, "translation_ms": 400},
            {"backend": "swift", "language": "ja", "success": False, "translation_ms": 1},
            {"backend": "rust", "language": "ja", "success": False, "translation_ms": 2},
        ]
    )
    assert result["swift/ja"] == {
        "attempts": 2,
        "successes": 1,
        "p50_ms": 400,
        "p95_ms": 400,
        "content_checked": 0,
        "content_passed": 0,
    }
    assert result["rust/ja"] == {
        "attempts": 1,
        "successes": 0,
        "p50_ms": None,
        "p95_ms": None,
        "content_checked": 0,
        "content_passed": 0,
    }


def test_meeting_translation_rejects_missing_chinese_time_and_invented_afternoon(monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    check = runpy.run_path(str(scripts / "benchmark_native_routes.py"))["tts_content_issues"]
    translation = {
        "zh": "Next meeting will start at three o'clock. 请带电脑。",
        "en": "The next meeting starts at 3 p.m. Please bring your computer.",
    }
    assert set(check("ja-tts", translation)) == {
        "missing_chinese_time",
        "missing_chinese_meeting",
        "invented_day_period",
    }
    faithful = {
        "zh": "下一次会议三点开始，请带电脑。",
        "en": "The next meeting starts at three o'clock. Please bring your computer.",
    }
    assert check("ja-tts", faithful) == []
    assert check("ja-natural-0", faithful) is None
