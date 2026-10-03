"""Real-model checks for early Chinese, prompt-cache reuse and context isolation.

Run with the subtitle service stopped; uses installed local models only.
"""

import json
import time
from pathlib import Path

from live_subs.engine import MLXEngine


def main():
    engine = MLXEngine(Path(".local/models.json"))
    cases = [
        ("次の会議は三時に始まります。パソコンを持ってきてください。", "ja"),
        ("次の会議は三時に始まります。", "ja"),
        ("パソコンを持ってきてください。", "ja"),
        ("The next meeting starts at three.", "en"),
        ("Please bring your laptop.", "en"),
    ]
    rows, expected = [], {}
    for mode in ("cold", "reuse"):
        for source, language in cases:
            if mode == "cold":
                engine.translation_caches.clear()
            started = time.perf_counter()
            progress = []

            def first(zh, started=started, progress=progress):
                progress.append({"zh": zh, "ms": round((time.perf_counter() - started) * 1000)})

            result = engine.translate(source, language, "zh-en", first)
            elapsed = round((time.perf_counter() - started) * 1000)
            assert len(progress) == 1 and progress[0]["zh"] == result["zh"]
            if mode == "cold":
                expected[source] = result
            else:
                assert result == expected[source], "复用缓存不能混入前一句或改变译文"
            if language == "ja":
                assert progress[0]["ms"] < elapsed, "中文应在英文生成完成前到达"
            row = dict(
                mode=mode,
                source=source,
                first_zh_ms=progress[0]["ms"],
                complete_ms=elapsed,
                **result,
            )
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    directory = Path(".local/benchmark")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "translation-stream.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
