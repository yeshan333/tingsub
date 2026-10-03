"""Bounded, frame-based endpoint detection. All time values are in audio seconds."""

from collections import deque
from dataclasses import dataclass, field
from time import monotonic

SAMPLE_RATE = 16000
FRAME_SAMPLES = 320
FRAME_BYTES = FRAME_SAMPLES * 2
FRAME_SECONDS = 0.02


@dataclass(frozen=True)
class AudioJob:
    id: int
    pcm: bytes
    start: float
    end: float
    final: bool
    # End of the last frame classified as speech (not the end of trailing silence).
    speech_end: float
    speech_start: float | None = None
    queued_at: float = field(default_factory=monotonic)


class Segmenter:
    """Keep 200 ms pre-roll; endpoint after 240 ms silence or 3 s of speech.

    Partial snapshots replace each other downstream. Forced boundaries do not overlap:
    every input frame belongs to one final segment, avoiding heuristic text deletion.
    """

    def __init__(self, *, silence_frames=12, max_frames=150, partial_frames=40):
        self.silence_frames = silence_frames
        self.max_frames = max_frames
        self.partial_frames = partial_frames
        self.pre = deque(maxlen=10)
        self.frames: list[bytes] = []
        self.clock = 0
        self.id = 0
        self.start = 0.0
        self.last_speech = 0.0
        self.first_speech = None
        self.end = 0.0
        self.previous_end = None
        self.voiced = self.silent = self.last_partial = 0
        self.continuation = False
        self.gaps = 0

    def feed(self, frame: bytes, speech: bool, end_seconds: float | None = None) -> list[AudioJob]:
        if len(frame) != FRAME_BYTES:
            raise ValueError("Expected exactly 20 ms of 16 kHz PCM16 mono")
        self.clock += 1
        end = self.clock * FRAME_SECONDS if end_seconds is None else end_seconds
        pending = []
        if self.previous_end is not None and abs(end - self.previous_end - FRAME_SECONDS) > 0.01:
            # Never stitch audio across a missing interval or backwards clock jump.
            pending = self.flush()
            self.pre.clear()
            self.gaps += 1
        self.previous_end = end
        self.end = end
        if not self.frames:
            if not speech:
                self.pre.append((frame, end))
                self.silent += 1
                if self.silent >= self.silence_frames:
                    self.continuation = False
                return pending
            self.id += 1
            self.start = (self.pre[0][1] if self.pre else end) - FRAME_SECONDS
            self.frames = [part for part, _ in self.pre]
            self.pre.clear()
            self.silent = 0
        self.frames.append(frame)
        if speech:
            self.voiced += 1
            self.silent = 0
            self.last_speech = end
            if self.first_speech is None:
                self.first_speech = end - FRAME_SECONDS
        else:
            self.silent += 1
        if self.silent >= self.silence_frames:
            return pending + self.flush()
        if len(self.frames) >= self.max_frames:
            return pending + self.flush(forced=True)
        if self.voiced >= 10 and len(self.frames) - self.last_partial >= self.partial_frames:
            self.last_partial = len(self.frames)
            return pending + [self._snapshot(False)]
        return pending

    def _snapshot(self, final: bool) -> AudioJob:
        return AudioJob(
            self.id,
            b"".join(self.frames),
            self.start,
            self.end,
            final,
            self.last_speech,
            self.first_speech,
        )

    def flush(self, *, forced=False) -> list[AudioJob]:
        # A short tail after a hard boundary belongs to already-confirmed speech.
        # Keep the 200ms gate only for a genuinely new utterance (e.g. a click).
        accepted = self.voiced >= 10 or (self.continuation and self.voiced > 0)
        result = [self._snapshot(True)] if accepted else []
        self.continuation = forced and accepted
        self.frames = []
        self.voiced = self.silent = self.last_partial = 0
        self.first_speech = None
        return result


class Mailbox:
    """At most three final segments plus one recent partial; never unbounded lag."""

    def __init__(self, limit=3):
        self.finals: deque[AudioJob] = deque()
        self.partial: AudioJob | None = None
        self.limit = limit
        self.finalized = 0
        self.dropped = 0

    def put(self, job: AudioJob) -> AudioJob | None:
        dropped = None
        if job.final:
            self.finalized = max(self.finalized, job.id)
            if self.partial and self.partial.id <= job.id:
                self.partial = None
            if len(self.finals) == self.limit:
                dropped = self.finals.popleft()
                self.dropped += 1
            self.finals.append(job)
        elif job.id > self.finalized:
            self.partial = job
        return dropped

    def pop(self) -> AudioJob | None:
        if self.finals:
            return self.finals.popleft()
        job, self.partial = self.partial, None
        return job
