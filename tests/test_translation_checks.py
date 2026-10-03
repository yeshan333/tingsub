"""Guard the real-model checker against misleading number-preservation passes."""

import runpy
from pathlib import Path

import pytest

checks = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/check_translation.py"))
CASES, check_result = checks["CASES"], checks["check_result"]


CONCERT = next(case for case in CASES if case.source.startswith("コンサート"))
MEETING = next(case for case in CASES if case.name == "日语明确下午的会议保留下午三点和电脑要求")


@pytest.mark.parametrize("hour,tickets", [("eight", "two"), ("8", "2"), ("8:00", "2")])
def test_concert_checker_accepts_eight_oclock_and_two_tickets_in_words_or_digits(hour, tickets):
    result = {
        "zh": "音乐会八点开始。有两张票。",
        "en": f"The concert starts at {hour}. There are {tickets} tickets.",
    }
    assert check_result(CONCERT, result) == []


@pytest.mark.parametrize(
    "field,text",
    [
        ("en", "The concert starts at 18. There are two tickets."),
        ("en", "The concert starts at eight. There are 20 tickets."),
        ("en", "The concert starts at 8:30. There are two tickets."),
        ("en", "The concert starts at eighteen. There are twenty tickets."),
        ("zh", "音乐会十八点开始。有两张票。"),
        ("zh", "音乐会八点开始。有十二张票。"),
        ("zh", "音乐会八点半开始。有两张票。"),
    ],
    ids=["18-not-8", "20-not-2", "8-30-not-8", "larger-number-words",
         "chinese-18-not-8", "chinese-12-not-2", "chinese-half-hour-not-whole-hour"],
)
def test_concert_checker_rejects_changed_hours_or_ticket_counts(field, text):
    result = {
        "zh": "音乐会八点开始。有两张票。",
        "en": "The concert starts at eight. There are two tickets.",
    }
    result[field] = text
    assert any(
        error.startswith(f"{field}: missing content") for error in check_result(CONCERT, result)
    )


@pytest.mark.parametrize("hour", ["3pm", "3:00 PM", "three in the afternoon"])
def test_explicit_afternoon_checker_accepts_correct_three_oclock_formats(hour):
    result = {
        "zh": "会议下午三点开始。请带电脑。",
        "en": f"The meeting starts at {hour}. Please bring your computer.",
    }
    assert check_result(MEETING, result) == []
