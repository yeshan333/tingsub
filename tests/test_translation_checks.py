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


MORNING = next(case for case in CASES if case.source.startswith("明日の午前"))
TECHNICAL = next(case for case in CASES if "OpenAI" in case.source)


def test_concert_checker_rejects_eight_tickets_at_two_instead_of_two_tickets_at_eight():
    result = {
        "zh": "音乐会八点开始。有两张票。",
        "en": "The concert starts at two. There are eight tickets.",
    }
    assert check_result(CONCERT, result)


@pytest.mark.parametrize(
    "case,chinese,english",
    [
        (MORNING, "明天上午八点在车站见。",
         "Tomorrow I am meeting you at eight at the station."),
        (MEETING, "会议下午三点开始。请带电脑。",
         "The meeting starts at three. Please bring your computer equipment."),
    ],
    ids=["verb-am-is-not-morning", "equipment-is-not-pm"],
)
def test_explicit_period_checker_rejects_ordinary_words_instead_of_am_or_pm(case, chinese, english):
    assert check_result(case, {"zh": chinese, "en": english})


@pytest.mark.parametrize("hour", ["8am", "8 a.m.", "eight in the morning"])
def test_explicit_morning_checker_accepts_time_adjacent_am_and_morning_words(hour):
    result = {
        "zh": "明天上午八点在车站见。",
        "en": f"Let's meet at the station at {hour} tomorrow.",
    }
    assert check_result(MORNING, result) == []


@pytest.mark.parametrize(
    "english,accepted",
    [
        ("This app does not use the OpenAI API.", True),
        ("This app doesn't use the OpenAI API.", True),
        ("This app is not using the OpenAI API.", True),
        ("The OpenAI API is not useful for this app.", False),
    ],
    ids=["does-not-use", "doesnt-use", "not-using", "not-useful-is-different"],
)
def test_technical_checker_preserves_not_using_instead_of_claiming_the_api_is_useless(
    english, accepted,
):
    result = {"zh": "这个应用没有使用OpenAI的API。", "en": english}
    assert (check_result(TECHNICAL, result) == []) is accepted


class CacheTrackingEngine:
    """Explicit fake for runner scheduling only; never used as model evidence."""

    def __init__(self):
        self.translation_caches = {}
        self.calls = []

    def translate(self, source, language, display):
        bilingual = language != "en" and display == "zh-en"
        self.calls.append((source, bilingual, bool(self.translation_caches.get(bilingual))))
        self.translation_caches[bilingual] = ([source], object())
        return {"zh": "译文", "en": source if language == "en" else "translation"}


def test_reuse_pass_seeds_both_prompt_variants_before_testing_the_first_bilingual_case(monkeypatch):
    case_type, run_cases = checks["Case"], checks["run_cases"]
    cases = [
        case_type("English", "English source", "en", ("译文",)),
        case_type("Japanese bilingual", "日语双语输入", "ja", ("译文",), ("translation",)),
        case_type("Original plus Chinese", "日语原文输入", "ja", ("译文",), display="source-zh"),
    ]
    monkeypatch.setitem(run_cases.__globals__, "CASES", cases)
    engine = CacheTrackingEngine()
    rows = run_cases(engine)
    assert len(rows) == 6  # Two warm-ups must not be counted as regression cases.
    assert all(not row["errors"] for row in rows)
    assert all(row["cached_tokens_before"] == 0 for row in rows if row["mode"] == "cold")
    assert all(row["cached_tokens_before"] > 0 for row in rows if row["mode"] == "reuse")
    assert engine.calls[-2] == ("日语双语输入", True, True)


def test_reuse_warmup_fails_if_the_engine_does_not_populate_both_prompt_variants():
    class MissingBilingualCache(CacheTrackingEngine):
        def translate(self, source, language, display):
            result = super().translate(source, language, display)
            self.translation_caches.pop(True, None)
            return result

    with pytest.raises(AssertionError, match="both prompt variants"):
        checks["prime_translation_caches"](MissingBilingualCache())
