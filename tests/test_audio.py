import struct

import pytest

from live_subs.audio import FRAME_BYTES, AudioJob, Mailbox, Segmenter


def frame(n):
    return struct.pack("<h", n) * 320


def test_silence_for_one_minute_never_emits_captions_and_keeps_only_preroll():
    segmenter = Segmenter()
    for _ in range(3000):
        assert segmenter.feed(bytes(FRAME_BYTES), False) == []
    assert len(segmenter.pre) == 10
    assert segmenter.frames == []


def test_sentence_retains_initial_consonants_and_finalizes_after_240ms_silence():
    segmenter = Segmenter()
    before = [frame(n) for n in range(10)]
    voice = [frame(n) for n in range(10, 35)]
    tail = [frame(n) for n in range(35, 47)]
    for part in before:
        assert segmenter.feed(part, False) == []
    for part in voice:
        segmenter.feed(part, True)
    for part in tail[:-1]:
        assert not any(job.final for job in segmenter.feed(part, False))
    [final] = segmenter.feed(tail[-1], False)
    assert final.final
    assert final.pcm == b"".join(before + voice + tail)
    assert final.start == 0
    assert final.speech_end == pytest.approx(0.7)
    assert final.end == pytest.approx(0.94)


def test_continuous_speech_emits_every_three_seconds_without_losing_or_repeating_audio():
    segmenter = Segmenter()
    source = [frame(n) for n in range(450)]
    finals = []
    for part in source:
        finals.extend(job for job in segmenter.feed(part, True) if job.final)
    finals.extend(segmenter.flush())
    assert [job.id for job in finals] == [1, 2, 3]
    assert b"".join(job.pcm for job in finals) == b"".join(source)
    assert [job.end for job in finals] == [3.0, 6.0, 9.0]
    assert max(len(job.pcm) for job in finals) <= FRAME_BYTES * 150


def test_short_click_is_not_treated_as_a_spoken_sentence():
    segmenter = Segmenter()
    for _ in range(3):
        segmenter.feed(frame(1000), True)
    assert segmenter.flush() == []


def test_speech_drafts_arrive_before_the_sentence_ends():
    segmenter = Segmenter()
    jobs = [job for _ in range(81) for job in segmenter.feed(frame(500), True)]
    assert len(jobs) == 2
    assert not any(job.final for job in jobs)
    assert jobs[0].end == pytest.approx(0.8)
    assert jobs[1].end == pytest.approx(1.6)
    assert jobs[0].id == jobs[1].id


def job(id, final=True):
    return AudioJob(id, b"", 0, 1, final, 1)


def test_overloaded_inference_discards_oldest_pending_sentence_and_reports_it():
    mailbox = Mailbox(limit=2)
    assert mailbox.put(job(1)) is None
    assert mailbox.put(job(2)) is None
    assert mailbox.put(job(3)).id == 1
    assert mailbox.dropped == 1
    assert [mailbox.pop().id, mailbox.pop().id] == [2, 3]
    assert mailbox.pop() is None


def test_final_sentence_supersedes_drafts_and_late_draft_cannot_return():
    mailbox = Mailbox()
    mailbox.put(job(1, False))
    mailbox.put(job(1))
    mailbox.put(job(1, False))
    assert mailbox.pop().final
    assert mailbox.pop() is None


def test_draft_queue_keeps_only_the_latest_audio_snapshot():
    mailbox = Mailbox()
    for id in range(100):
        mailbox.put(job(id + 1, False))
    assert mailbox.pop().id == 100
    assert mailbox.pop() is None


@pytest.mark.parametrize("speech_frames", [155, 303])
@pytest.mark.parametrize("stop_immediately", [False, True])
def test_short_speech_tail_after_hard_cut_reaches_asr_on_silence_or_stop(
    speech_frames,
    stop_immediately,
):
    segmenter = Segmenter()
    speech = [frame(n + 100) for n in range(speech_frames)]
    finals = [job for part in speech for job in segmenter.feed(part, True) if job.final]
    silence = [] if stop_immediately else [frame(0)] * 12
    finals += [job for part in silence for job in segmenter.feed(part, False) if job.final]
    finals += segmenter.flush()
    assert b"".join(job.pcm for job in finals) == b"".join(speech + silence)
    assert finals[-1].speech_end == pytest.approx(speech_frames * 0.02)


def test_short_click_after_a_completed_utterance_still_does_not_become_speech():
    segmenter = Segmenter()
    for _ in range(150):
        segmenter.feed(frame(500), True)
    for _ in range(12):
        segmenter.feed(frame(0), False)
    for _ in range(3):
        segmenter.feed(frame(1000), True)
    assert segmenter.flush() == []


def test_audio_gap_finishes_previous_speech_and_uses_fresh_frame_timestamps():
    segmenter = Segmenter()
    old, new = frame(100), frame(200)
    for n in range(15):
        segmenter.feed(old, True, (n + 1) * 0.02)
    [before_gap] = segmenter.feed(new, True, 3.32)
    for n in range(14):
        segmenter.feed(new, True, 3.34 + n * 0.02)
    [after_gap] = segmenter.flush()
    assert segmenter.gaps == 1
    assert before_gap.pcm == old * 15
    assert after_gap.pcm == new * 15
    assert before_gap.end == pytest.approx(0.30)
    assert after_gap.start == pytest.approx(3.30)
    assert after_gap.end == pytest.approx(3.60)
    assert after_gap.id != before_gap.id
