import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from live_subs.audio import AudioJob
from live_subs.pipeline import Pipeline


class ScriptedEngine:
    """A deterministic adapter for scheduling tests, not an ASR quality test."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def transcribe(self, pcm, language):
        self.calls.append(("asr", pcm))
        return pcm.decode(), language

    def translate(self, source, language, display, on_chinese=None):
        self.calls.append(("translate", source))
        if self.fail:
            raise RuntimeError("model unavailable")
        return {"zh": "你好", "en": "Hello"}


async def test_final_caption_shows_source_before_translation_and_preserves_sentence_identity():
    events = []

    async def send(event):
        events.append(event)

    with ThreadPoolExecutor(max_workers=1) as executor:
        epoch = time.time() * 1000
        pipeline = Pipeline(ScriptedEngine(), executor, send, "ja", "zh-en", epoch)
        await pipeline.submit(AudioJob(1, "こんにちは".encode(), 0, 1, True, 0.8))
        pipeline.finish()
        await pipeline.run()
    assert [event["type"] for event in events] == ["transcript", "translation", "done"]
    assert events[0]["id"] == events[1]["id"] == 1
    assert events[1]["source"] == "こんにちは"
    assert events[1]["zh"] == "你好" and events[1]["en"] == "Hello"
    assert events[1]["speech_end_ms"] == epoch + 800


async def test_failed_local_translation_is_reported_without_fabricating_a_translation():
    events = []

    async def send(event):
        events.append(event)

    with ThreadPoolExecutor(max_workers=1) as executor:
        pipeline = Pipeline(
            ScriptedEngine(fail=True),
            executor,
            send,
            "en",
            "zh-en",
            time.time() * 1000,
        )
        await pipeline.submit(AudioJob(1, b"Hello", 0, 1, True, 1))
        pipeline.finish()
        await pipeline.run()
    assert [event["type"] for event in events] == ["transcript", "error", "done"]
    assert events[1]["message"] == "model unavailable"


async def test_final_arriving_during_draft_inference_suppresses_the_obsolete_draft():
    events = []
    began = asyncio.Event()
    release = __import__("threading").Event()
    loop = asyncio.get_running_loop()

    class SlowDraft(ScriptedEngine):
        def transcribe(self, pcm, language):
            if pcm == b"draft":
                loop.call_soon_threadsafe(began.set)
                assert release.wait(3)
            return pcm.decode(), language

    async def send(event):
        events.append(event)

    with ThreadPoolExecutor(max_workers=1) as executor:
        pipeline = Pipeline(SlowDraft(), executor, send, "en", "zh-en", time.time() * 1000)
        await pipeline.submit(AudioJob(1, b"draft", 0, 0.8, False, 0.8))
        task = asyncio.create_task(pipeline.run())
        await asyncio.wait_for(began.wait(), 3)
        await pipeline.submit(AudioJob(1, b"complete", 0, 1, True, 1))
        release.set()
        pipeline.finish()
        await asyncio.wait_for(task, 3)
    assert [event["type"] for event in events] == ["transcript", "translation", "done"]
    assert events[0]["source"] == "complete"


async def test_sentence_waiting_too_long_is_explicitly_skipped_even_before_queue_fills():
    events = []

    async def send(event):
        events.append(event)

    engine = ScriptedEngine()
    with ThreadPoolExecutor(max_workers=1) as executor:
        pipeline = Pipeline(engine, executor, send, "en", "zh-en", time.time() * 1000 - 10000)
        await pipeline.submit(AudioJob(1, b"old speech", 0, 1, True, 1))
        pipeline.finish()
        await pipeline.run()
    assert engine.calls == []
    assert [event["type"] for event in events] == ["dropped", "done"]
    assert events[0]["id"] == 1


async def test_fresh_audio_after_three_second_gap_is_transcribed_instead_of_discarded():
    from live_subs.audio import Segmenter

    segmenter = Segmenter(partial_frames=10000)
    old, new = b"a" * 640, b"b" * 640
    for n in range(15):
        segmenter.feed(old, True, (n + 1) * 0.02)
    jobs = segmenter.feed(new, True, 3.32)
    for n in range(14):
        jobs += segmenter.feed(new, True, 3.34 + n * 0.02)
    jobs += segmenter.flush()
    events = []

    async def send(event):
        events.append(event)

    engine = ScriptedEngine()
    with ThreadPoolExecutor(max_workers=1) as executor:
        pipeline = Pipeline(engine, executor, send, "en", "zh-en", time.time() * 1000 - 3600)
        for job in jobs:
            await pipeline.submit(job)
        pipeline.finish()
        await pipeline.run()
    assert [event["id"] for event in events if event["type"] == "dropped"] == [1]
    assert [event["id"] for event in events if event["type"] == "translation"] == [2]
    assert engine.calls[0] == ("asr", new * 15)


async def test_chinese_is_delivered_while_english_generation_is_still_blocked():
    import threading

    release = threading.Event()
    events = []

    class StreamingEngine(ScriptedEngine):
        def translate(self, source, language, display, on_chinese=None):
            on_chinese("你好")
            assert release.wait(3), "Chinese must reach the client before final translation exists"
            return {"zh": "你好", "en": "Hello"}

    async def send(event):
        events.append(event)
        if event["type"] == "translation_progress":
            assert not any(e["type"] == "translation" for e in events)
            release.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        pipeline = Pipeline(
            StreamingEngine(), executor, send, "ja", "zh-en", time.time() * 1000 - 1000
        )
        await pipeline.submit(AudioJob(1, b"hello", 0, 1, True, 0.8, 0.1))
        pipeline.finish()
        await asyncio.wait_for(pipeline.run(), 4)
    assert [e["type"] for e in events] == [
        "transcript",
        "translation_progress",
        "translation",
        "done",
    ]
    assert events[1]["zh"] == "你好" and events[1]["en"] == ""
    assert events[2]["en"] == "Hello"
    assert events[2]["first_zh_ms"] >= events[2]["first_text_ms"]
    assert events[2]["metrics"]["counts"]["translated"] == 1


async def test_low_confidence_rejection_is_counted_separately_from_silence():
    from live_subs.engine import Recognition

    class UncertainEngine(ScriptedEngine):
        def transcribe(self, *_):
            return Recognition("", "ja", "low_confidence")

    events = []

    async def send(event):
        events.append(event)

    with ThreadPoolExecutor(max_workers=1) as executor:
        pipeline = Pipeline(UncertainEngine(), executor, send, "ja", "zh-en", time.time() * 1000)
        await pipeline.submit(AudioJob(1, b"audio", 0, 1, True, 1))
        pipeline.finish()
        await pipeline.run()
    assert [e["type"] for e in events] == ["rejected", "done"]
    assert events[0]["reason"] == "low_confidence"
    assert events[0]["metrics"]["counts"] == {"segments": 1, "low_confidence": 1}
