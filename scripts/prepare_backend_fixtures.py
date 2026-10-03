"""Download the first three viewer rows per corpus plus two macOS TTS fixtures.

Audio and references remain in ignored .local. No private audio is collected.
"""

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import httpx

CORPORA = {
    "en": ("hf-internal-testing/librispeech_asr_dummy", "clean", "validation", "text"),
    "ja": ("japanese-asr/ja_asr.jsut_basic5000", "default", "test", "transcription"),
}
SPEECH = {
    "en": ("Samantha", "The next meeting starts at three o'clock. Please bring your laptop."),
    "ja": ("Kyoko", "次の会議は三時に始まります。パソコンを持ってきてください。"),
}


def main():
    directory = Path(".local/backend-fixtures")
    directory.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        for language, (dataset, config, split, column) in CORPORA.items():
            response = client.get(
                "https://datasets-server.huggingface.co/rows",
                params={
                    "dataset": dataset,
                    "config": config,
                    "split": split,
                    "offset": 0,
                    "length": 3,
                },
            )
            response.raise_for_status()
            for item in response.json()["rows"]:
                index, row = item["row_idx"], item["row"]
                identity = f"{language}-natural-{index}"
                url = row["audio"][0]["src"]
                revision = url.split("/--/")[1]
                audio = client.get(url)
                audio.raise_for_status()
                original = directory / (identity + ".download")
                original.write_bytes(audio.content)
                target = directory / (identity + ".wav")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-y",
                        "-i",
                        str(original),
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        "-c:a",
                        "pcm_s16le",
                        str(target),
                    ],
                    check=True,
                )
                fixtures.append(
                    {
                        "id": identity,
                        "file": target.name,
                        "language": language,
                        "reference": row[column],
                        "kind": "human read speech",
                        "dataset": dataset,
                        "config": config,
                        "split": split,
                        "row": index,
                        "revision": revision,
                        "download_sha256": hashlib.sha256(audio.content).hexdigest(),
                    }
                )
    for language, (voice, text) in SPEECH.items():
        target = directory / f"{language}-tts.wav"
        subprocess.run(
            [
                "say",
                "-v",
                voice,
                "-r",
                "175",
                "-o",
                str(target),
                "--file-format=WAVE",
                "--data-format=LEI16@16000",
                text,
            ],
            check=True,
        )
        fixtures.append(
            {
                "id": f"{language}-tts",
                "file": target.name,
                "language": language,
                "reference": text,
                "kind": "macOS TTS",
                "voice": voice,
            }
        )
    for fixture in fixtures:
        path = directory / fixture["file"]
        fixture["pcm_file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with wave.open(str(path)) as f:
            fixture["duration_seconds"] = f.getnframes() / f.getframerate()
    (directory / "manifest.json").write_text(
        json.dumps({"fixtures": fixtures}, ensure_ascii=False, indent=2)
    )
    print(json.dumps([{k: f[k] for k in ["id", "duration_seconds"]} for f in fixtures], indent=2))


if __name__ == "__main__":
    main()
