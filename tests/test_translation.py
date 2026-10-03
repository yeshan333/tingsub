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


def test_chinese_in_original_mode_bypasses_model_imports_and_preserves_recognized_text(monkeypatch):
    import sys

    from live_subs.engine import MLXEngine

    monkeypatch.setitem(sys.modules, "mlx_lm", None)
    engine = object.__new__(MLXEngine)
    observed = []
    source = "时间是六点，不是七点。"
    assert engine.translate(source, "zh", "source-zh", observed.append) == {"zh": source, "en": ""}
    assert observed == [source]


def test_chinese_bilingual_output_ignores_rewritten_chinese_and_requires_english():
    source = "我不确定，可能是六点。"
    assert parse_translation('{"zh":"错误改写","en":"It may be six."}', source, "zh", "zh-en") == {
        "zh": source,
        "en": "It may be six.",
    }
    with pytest.raises(ValueError, match="英文译文"):
        parse_translation('{"zh":"改写"}', source, "zh", "zh-en")


def test_chinese_is_emitted_before_english_only_generation_and_uses_a_separate_cache(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace

    from live_subs.engine import MLXEngine

    # Protocol adapter only: no claims about model translation quality.
    observed, prompts = [], []
    source = "请保留 42 这个数字。"

    def generate(*args, **kwargs):
        assert observed == [source], "Chinese must be available before English inference"
        assert prompts[0][-1]["content"] == '{"en":'
        assert "只输出 en 字段" in prompts[0][0]["content"]
        yield SimpleNamespace(text='"Please keep the number 42."}')

    modules = {
        name: ModuleType(name) for name in ("mlx_lm", "mlx_lm.models.cache", "mlx_lm.sample_utils")
    }
    modules["mlx_lm"].stream_generate = generate
    modules["mlx_lm.models.cache"].make_prompt_cache = lambda _: [SimpleNamespace(offset=0)]
    modules["mlx_lm.models.cache"].trim_prompt_cache = lambda *_: None
    modules["mlx_lm.sample_utils"].make_sampler = lambda **_: None
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    engine = object.__new__(MLXEngine)
    engine.model = object()
    engine.translation_caches = {}

    def template(messages, **_):
        prompts.append(messages)
        return "prompt"

    engine.tokenizer = SimpleNamespace(
        apply_chat_template=template, encode=lambda *_a, **_k: [1, 2]
    )
    result = engine.translate(source, "zh", "zh-en", observed.append)
    assert result == {"zh": source, "en": "Please keep the number 42."}
    assert observed == [source]
    assert set(engine.translation_caches) == {"en"}
