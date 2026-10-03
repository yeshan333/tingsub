import zlib

from live_subs.engine import reliable_transcript


def test_music_induced_repetition_is_discarded_instead_of_filling_the_caption_overlay():
    text = "また石井にも大きな" + "井" * 180
    encoded = text.encode("utf-8")
    result = {
        "text": text,
        "segments": [{"compression_ratio": len(encoded) / len(zlib.compress(encoded)),
                      "avg_logprob": -0.3}],
    }
    assert reliable_transcript(result) == ""


def test_low_confidence_recognition_is_not_presented_as_a_spoken_sentence():
    assert reliable_transcript({
        "text": "Invented speech.",
        "segments": [{"compression_ratio": 1.1, "avg_logprob": -1.2}],
    }) == ""


def test_valid_repeated_cheering_is_preserved_when_decoder_quality_is_acceptable():
    assert reliable_transcript({
        "text": " Go! Go! Go! ",
        "segments": [{"compression_ratio": 0.8, "avg_logprob": -0.2}],
    }) == "Go! Go! Go!"


def test_one_failed_segment_discards_the_chunk_without_presenting_a_misleading_partial_sentence():
    assert reliable_transcript({
        "text": "The winner is noise noise noise",
        "segments": [
            {"compression_ratio": 1, "avg_logprob": -0.2},
            {"compression_ratio": 3.5, "avg_logprob": -0.3},
        ],
    }) == ""
