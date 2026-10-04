[English](../en/asr-comparison-2026-10-05.md) · [简体中文](../zh-CN/asr-comparison-2026-10-05.md) · [Benchmarks](benchmarks.md)

# Whisper and Qwen3-ASR: local recognition comparison

**Tested 2026-10-05. Recommendation: keep Whisper Turbo as the default and consider Qwen3-ASR 0.6B for a future optional fast mode.** Recognition was substantially faster with 0.6B, but it made more errors on these Japanese recordings. The 1.7B model did not consistently win and used more memory.

Qwen3-ASR **is not integrated into TingSub's desktop model list or production recognition backend**. This report covers a separate Python / MLX Audio experiment, not a released feature. The existing `prepare --asr` option cannot enable it directly. See [models](models.md) for currently available choices.

## What users might notice

On this M4 Pro, 0.6B reduced median recognition time for human speech from 527 ms to 234 ms. With the same translation model, complete bilingual output fell from 906 ms to 672 ms. That saves inference time, but does not mean captions appear 672 ms after someone starts speaking: capture, pause detection, queuing and browser display are excluded.

Only six human read-speech recordings were tested. They cannot establish general accuracy. For example, the Japanese word for an archipelago became an army or a naval port: the faster caption also changed the meaning. Keep the default while evaluating an optional 0.6B integration; 1.7B is not the immediate priority.

## Speed and memory

Hardware: Apple M4 Pro, 48 GiB RAM, macOS 27.0.1. Every group used the same Qwen2.5-3B-Instruct 4-bit translation model and TingSub translation method. Values below are medians over two warmed-up rounds.

| Recognition model | Human ASR | Human complete bilingual | Synthetic short ASR | Synthetic complete bilingual | MLX peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Whisper Turbo 4-bit | 527 ms | 906 ms | 521 ms | 818 ms | 3.08 GB |
| Qwen3-ASR 0.6B 8-bit | 234 ms | 672 ms | 120 ms | 415 ms | 3.68 GB |
| Qwen3-ASR 1.7B 8-bit | 391 ms | 713 ms | 238 ms | 539 ms | 5.34 GB |

- Human speech: three English and three Japanese clips, 6.96–11.46 seconds long, giving 12 timings per model. Six synthetic short clips also give 12 timings per model.
- Complete bilingual time starts with complete PCM ready for recognition and ends after translation returns, including minor result-checking overhead. It is not first-text, first-token or speech-end latency. Audio reading, loading and warm-up are excluded.
- MLX allocator peak includes recognition and translation, in decimal GB. It is not total application/system memory or download size. Here, 0.6B is faster but does not use less memory.
- Silence and the two synthetic-accompaniment clips are separate groups, excluded from this table. See the [machine-readable results](../benchmarks/asr-2026-10-05.json) for individual timings, complete-Chinese timing, RSS and ranges.

### Rechecks and environmental effects

Background-process monitoring for the initial Whisper / 0.6B runs targeted an exited PID, so it cannot establish idle background conditions. The 1.7B weights were also still downloading. After correcting monitoring and completing the download, each model received one additional round. Human ASR / complete bilingual medians were **515 / 871 ms for Whisper** and **184 / 488 ms for 0.6B**. Rechecks confirmed the direction of the speed difference but also showed timing variability. The table retains the initial two rounds instead of substituting the faster run.

Another application's local inference service remained running. Its cumulative CPU time did not increase during either recheck and increased by 0.01 seconds during the 1.7B run. This was not comprehensive system GPU monitoring. Rechecks are stored separately and do not increase the number of independent quality samples.

## Recognition quality and failures

Error rates use only the first round of six clean human recordings. Repeated rounds are not additional samples. English word error rate (WER) and Japanese character error rate (CER) measure different units and should not be compared across languages.

| Recognition model | English WER (3 clips) | Japanese CER (3 clips) | Synthetic semantic checks (6 clips) | Silence control |
| --- | ---: | ---: | ---: | --- |
| Whisper Turbo | 5.5% (4/73) | 3.1% (3/96) | 5/6 | Produced `you` |
| Qwen3-ASR 0.6B | 5.5% (4/73) | 8.3% (8/96) | 6/6 | Empty |
| Qwen3-ASR 1.7B | 4.1% (3/73) | 6.2% (6/96) | 5/6 | Empty |

Parentheses show edits / reference units; percentages are rounded. Text is normalized with NFKC, English lowercasing and punctuation handling before edit-distance scoring. Numbers/kanji, plurals and reference annotations were not corrected: reference `year` versus recognized `years` counts as one error. WER/CER do not score meaning or translation, and passing 6/6 synthetic checks does not establish natural-speech accuracy.

| Human Japanese content | Whisper | 0.6B | 1.7B |
| --- | --- | --- | --- |
| 群島 (archipelago) | Correct | 軍隊 (army) | 軍港 (naval port) |
| 敵対的環境コース | Correct | コース became 構築 | 敵対的 became 適体適 |
| 横柄 (arrogant) | 法兵 | 暴兵 | Correct |

- All three missed the German word `Sie` embedded in English speech. In another clip, 1.7B correctly recognized `splendours`.
- For synthetic `OpenAI`, 0.6B was correct, Whisper produced `Openay`, and 1.7B produced `オペネイ`. All preserved the negative statement about not using the API. Synthetic pronunciation is not representative of every human pronunciation.
- Silence was passed directly to the models, bypassing voice activity detection (VAD). This probes hallucinated speech; it does not mean the production overlay necessarily displays that output.
- Two human recordings were mixed with synthetic accompaniment at 10 dB signal-to-noise ratio. Their main errors matched the clean recordings; this does not establish robustness to real livestream music.
- Outputs were identical across the two main rounds. There were no inference exceptions, including rechecks. Language identification was correct for all voiced clips; Qwen never reached its 128-token limit. Failed semantic checks were retained without retries or dropping difficult cases.

### Correct recognition can still lead to incorrect translation

All three correctly recognized “25 to 30 years,” but the unchanged Qwen2.5-3B translator rendered the range as 25 to 35 years in Chinese. With 0.6B, correctly recognized `Lord Byron` became “路易·波拿巴勋爵” in Chinese. Whisper's corresponding Chinese output retained `glowing`, while 1.7B's translation was correct. These are translation-stage errors and show sensitivity to small transcription differences. Replacing recognition alone cannot guarantee a fix.

## Method and versions

Source baseline: `1667a47236f47e727145044ce2aee985cb4cf8f9`. Python 3.12.11, MLX 0.32.3, MLX LM 0.32.0 and MLX Whisper 0.4.3; the separate Qwen environment additionally used MLX Audio 0.5.7. Per-run dependency versions are in the results file.

| Model repository | Pinned revision |
| --- | --- |
| `mlx-community/whisper-large-v3-turbo-4bit` | `0f058d38170d183f9fdee07908f5b515d91793a8` |
| `mlx-community/Qwen3-ASR-0.6B-8bit` | `89e96d92ba34aca20b3e29fb10cc284097d1219f` |
| `mlx-community/Qwen3-ASR-1.7B-8bit` | `a8379a2e2f9e313c9292cdf1af4055ab56d50d55` |
| `mlx-community/Qwen2.5-3B-Instruct-4bit` | `4f83f8f146fdf28b512a06562b671d7af4fab457` |

1. From the [pinned FLEURS dataset](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd), take the first three recordings in archive order from each of the `en_us` / `ja_jp` test sets with duration 4–12 seconds and distinct utterance IDs. Selection preceded inference, used dataset references and did not depend on model performance.
2. Convert complete recordings to 16 kHz mono PCM16. Add six macOS `say` semantic-control clips, one digitally generated silence clip and two synthetic-accompaniment variants: 15 audio inputs in total.
3. Load each recognition model separately. Warm recognition with separate English/Japanese phrases and translation caches with `Hello.` / `こんにちは。`. Use automatic language detection, temperature zero and a 128-token generation limit.
4. Whisper uses TingSub's recognition method; Qwen uses MLX Audio's complete-audio `generate`. All reuse TingSub's translation method, prompt and early-Chinese callback. Japanese produces Chinese and English; English preserves the recognized source and adds Chinese.
5. Run fixed order, then reverse order: 90 main measurements. Two additional single-model recheck rounds add 30 calls. There is no browser capture, live queue or streaming segmentation, so no rejection/drop rate or livestream P95 is reported. All 120 calls completed without inference exceptions, but some content checks failed as described above.

Complete 6.96–11.46-second read-speech clips differ from the application's roughly three-second forced splits during continuous speech. Swift integration, incremental audio, overlapping speakers, fast livestream speech and long sessions were not tested. Results also do not establish native `mlx-serve` compatibility.

## Evidence and future updates

The [results JSON](../benchmarks/asr-2026-10-05.json) contains all 120 timings, error counts, summaries, sample archive locations and SHA256 hashes. Private paths, background application details, full transcripts and audio are excluded. `asr_token_limit_reached: null` means the metric was not recorded for that call, not that truncation was ruled out. Full outputs and one-off experiment scripts remain local to the maintainer. The published snapshot supports recalculating the aggregates; it is not yet a one-command public evaluation harness.

For future tests, add dated English and Chinese reports linked from [benchmarks](benchmarks.md) and preserve this snapshot. Include implementation status, performance and quality on identical inputs, sample counts, versions, failure cases and untested conditions. If a new run improves number or name translation, retest the failing audio and link the new evidence rather than relabeling old failures as fixed.
