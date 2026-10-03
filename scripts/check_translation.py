"""Check translation fidelity with installed local models; no mocks or downloads.

Stop the subtitle service first to avoid competing for the GPU. These authored
examples guard specific regressions, not general translation quality.
"""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from live_subs.engine import MLXEngine


@dataclass(frozen=True)
class Case:
    name: str
    source: str
    language: str
    zh: tuple[str, ...]
    en: tuple[str, ...] = ()
    ambiguous_time: bool = False
    display: str = "zh-en"
    latin_names: tuple[str, ...] = ()


# Match complete numeric values: 8 must not match 18, nor 十点 match 二十点.
ZH_DIGITS = "零〇一二两三四五六七八九十百千0123456789"


def chinese_hour(hour: str) -> str:
    return rf"(?<![{ZH_DIGITS}]){hour}点(?![{ZH_DIGITS}半刻])"


def english_hour(word: str, number: int) -> str:
    return rf"(?<![\w.])(?:{word}\b|{number}(?:[:.]00)?(?!\d|[:.]\d))"


CASES = [
    Case("英文单词 you 保留原文并译为中文", "you", "en", ("你",)),
    Case("英文音乐标记保留原文并译为中文", "Music", "en", ("音乐",)),
    Case("英文短感叹保留原文并译为中文", "Oh!", "en", ("哦",)),
    Case(
        "日语单句会议保留三点且不补时段",
        "次の会議は三時に始まります。", "ja",
        ("会议", chinese_hour("三"), "开始"), ("meeting", english_hour("three", 3), "start|begin"),
        ambiguous_time=True,
    ),
    Case(
        "日语请求携带电脑译出完整要求",
        "パソコンを持ってきてください。", "ja",
        ("带|拿", "电脑"), ("bring", "computer|laptop"),
    ),
    Case(
        "日语两句会议和电脑要求均译为中英且不补时段",
        "次の会議は三時に始まります。パソコンを持ってきてください。", "ja",
        ("会议", chinese_hour("三"), "开始", "带", "电脑"),
        ("meeting", english_hour("three", 3), "start|begin", "bring", "computer|laptop"),
        ambiguous_time=True,
    ),
    Case(
        "日语明确下午的会议保留下午三点和电脑要求",
        "会議は午後三時に始まります。パソコンを持ってきてください。", "ja",
        ("会议", "下午" + chinese_hour("三"), "开始", "带", "电脑"),
        ("meeting", english_hour("three", 3), r"afternoon|p\.?m", "bring", "computer|laptop"),
    ),
    Case(
        "日语明确明天上午的约定保留日期时段和地点",
        "明日の午前八時に駅で会いましょう。", "ja",
        ("明天", "(?:上午|早上)" + chinese_hour("八"), "站", "见|会面"),
        ("tomorrow", english_hour("eight", 8), r"morning|a\.?m", "station", "meet"),
    ),
    Case(
        "日语两句否定保留没有会议和计划未定",
        "今日は会議はありません。明日の予定はまだ決まっていません。", "ja",
        ("今天没有会议", "明天", "还没有|尚未|未定", "确定|决定|定"),
        ("no meeting", "today", "tomorrow", "not.*(?:decided|determined|set|fixed)"),
    ),
    Case(
        "英文两句保留原文并完整译成中文且不补时段",
        "The next meeting starts at three o'clock. Please bring your laptop.", "en",
        ("会议", chinese_hour("三"), "开始", "带", "电脑"), ambiguous_time=True,
    ),
    Case(
        "日语商店开门和现金要求均保留且不补时段",
        "店は十時に開きます。現金を持ってきてください。", "ja",
        ("店", chinese_hour("十"), "开", "现金", "带"),
        ("store|shop", english_hour("ten", 10), "open", "cash", "bring"), ambiguous_time=True,
    ),
    Case(
        "日语音乐会时间和两张票均保留且不补时段",
        "コンサートは八時に始まります。チケットは二枚あります。", "ja",
        ("音乐会|演唱会", chinese_hour("八"), "开始", rf"(?<![{ZH_DIGITS}])(?:两|二)张", "票"),
        ("concert", english_hour("eight", 8), "start|begin", r"\b(?:two|2)\b", "ticket"),
        ambiguous_time=True,
    ),
    Case(
        "日语技术名称保留拉丁专名且保留未使用的否定",
        "このアプリはOpenAIのAPIを使っていません。", "ja",
        ("应用", "OpenAI", "API", "没有使用|未使用|不使用"),
        ("app", "OpenAI", "API", "not use|not using|doesn't use"),
        latin_names=("OpenAI", "API"),
    ),
    Case(
        "日语原文加中文模式也完整翻译两句且不补时段",
        "次の会議は三時に始まります。パソコンを持ってきてください。", "ja",
        ("会议", chinese_hour("三"), "开始", "带", "电脑"),
        ambiguous_time=True, display="source-zh",
    ),
]


def check_result(case: Case, result: dict) -> list[str]:
    errors = []
    for field, patterns in (("zh", case.zh), ("en", case.en)):
        for pattern in patterns:
            if not re.search(pattern, result[field], re.IGNORECASE):
                errors.append(f"{field}: missing content matching {pattern!r}")
    # Only these authored examples have a known list of allowed Latin names.
    # This is NOT a production language detector or a general translation score.
    chinese = result["zh"]
    for name in case.latin_names:
        chinese = chinese.replace(name, "")
    if re.search(r"[a-zA-Z\u3040-\u30ff]", chinese):
        errors.append("zh: untranslated English/Japanese outside allowed names")
    if case.language == "en" and result["en"] != case.source:
        errors.append("en: English source was rewritten")
    if case.language != "en" and case.display == "zh-en":
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", result["en"]):
            errors.append("en: untranslated Japanese/Chinese")
    if case.ambiguous_time:
        if re.search("上午|下午|早上|早晨|凌晨|中午|傍晚|晚上|夜里", result["zh"]):
            errors.append("zh: invented time of day")
        if re.search(
            r"(?<![a-z])(?:a\.?\s*m\.?|p\.?\s*m\.?)(?![a-z])"
            r"|\b(?:morning|afternoon|evening|night|noon|midnight)\b",
            result["en"], re.IGNORECASE,
        ):
            errors.append("en: invented time of day")
    return errors


def main():
    model_file = Path(".local/models.json")
    engine = MLXEngine(model_file)
    rows = []
    for mode in ("cold", "reuse"):
        # Reverse the second pass to exercise changed preceding text and both
        # cache branches; do not require bit-identical text from GPU arithmetic.
        for case in CASES if mode == "cold" else reversed(CASES):
            if mode == "cold":
                engine.translation_caches.clear()
            start = time.perf_counter()
            try:
                result = engine.translate(case.source, case.language, case.display)
                errors = check_result(case, result)
            except Exception as exc:
                result, errors = {}, [f"{type(exc).__name__}: {exc}"]
            elapsed = round((time.perf_counter() - start) * 1000)
            rows.append(dict(mode=mode, name=case.name, ms=elapsed, result=result, errors=errors))
            status = "FAIL" if errors else "PASS"
            print(f"{status} [{mode}] {case.name} ({elapsed}ms): {result}", flush=True)
            for error in errors:
                print(f"  {error}", flush=True)
    config = json.loads(model_file.read_text())
    report = {
        "translation_model": {k: config["translation"][k] for k in ("repo", "revision")},
        "rows": rows,
    }
    path = Path(".local/benchmark/translation-check.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    failures = sum(bool(row["errors"]) for row in rows)
    print(f"{len(rows) - failures}/{len(rows)} passed; report: {path}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
