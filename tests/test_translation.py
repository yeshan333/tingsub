import pytest

from live_subs.engine import parse_translation


def test_english_speech_keeps_verbatim_source_as_english_caption():
    value = parse_translation('{"zh":"你好","en":"rewritten"}', "Hello!", "en", "zh-en")
    assert value == {"zh": "你好", "en": "Hello!"}


def test_japanese_speech_requires_both_chinese_and_english_in_bilingual_mode():
    with pytest.raises(ValueError, match="英文译文"):
        parse_translation('{"zh":"你好"}', "こんにちは", "ja", "zh-en")
    assert parse_translation(
        '```json\n{"zh":"你好","en":"Hello"}\n```',
        "こんにちは",
        "ja",
        "zh-en",
    ) == {"zh": "你好", "en": "Hello"}


def test_original_plus_chinese_mode_does_not_require_an_extra_english_translation():
    assert parse_translation('{"zh":"你好"}', "こんにちは", "ja", "source-zh")["zh"] == "你好"


@pytest.mark.parametrize("raw", ["{}", "not json", '{"zh":42}', '{"zh":""}'])
def test_invalid_model_output_is_an_error_instead_of_a_successful_caption(raw):
    with pytest.raises(ValueError):
        parse_translation(raw, "Hello", "en", "zh-en")


@pytest.mark.parametrize("raw", ['{"zh":', '{"zh":"未完成', '{"zh":42'])
def test_incomplete_or_non_string_chinese_is_never_exposed_as_streamed_caption(raw):
    from live_subs.engine import completed_chinese

    assert completed_chinese(raw) is None


def test_complete_chinese_json_string_can_be_shown_before_english_is_available():
    from live_subs.engine import completed_chinese

    assert completed_chinese('{"zh":"他说\\"你好\\"","en":') == '他说"你好"'
