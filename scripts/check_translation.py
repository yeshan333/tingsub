"""Run translation regressions with the installed local model; no mock or download.

Run while the subtitle service is stopped to avoid competing for the GPU.
"""

import re
import time
from pathlib import Path

from live_subs.engine import MLXEngine


def main():
    engine = MLXEngine(Path(".local/models.json"))
    cases = [
        ("直播单词 you 必须返回中文译文及原英文", "you", "en", "你", "you"),
        ("直播音乐标记必须返回中文译文及原英文", "Music", "en", "音乐", "Music"),
        ("英文短感叹必须返回中英字幕", "Oh!", "en", "哦", "Oh!"),
        (
            "日语会议时间必须保留三点且不擅自补充上午下午",
            "次の会議は三時に始まります。", "ja", "三点", "three",
        ),
        (
            "日语携带电脑的要求必须译为中文和英文",
            "パソコンを持ってきてください。", "ja", "电脑", "computer",
        ),
    ]
    for name, source, language, expected_zh, expected_en in cases:
        start = time.perf_counter()
        result = engine.translate(source, language, "zh-en")
        assert expected_zh in result["zh"], (name, result)
        assert expected_en in result["en"], (name, result)
        if language == "en":
            assert result["en"] == source, (name, result)
        if "時間" in source or "三時" in source:
            assert "上午" not in result["zh"] and "下午" not in result["zh"], (name, result)
            assert not re.search(r"\b(?:am|pm)\b", result["en"].lower().replace(".", "")), (
                name, result,
            )
        print(f"PASS {name} ({(time.perf_counter() - start) * 1000:.0f}ms): {result}", flush=True)


if __name__ == "__main__":
    main()
