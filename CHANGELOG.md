# Changelog

[English](CHANGELOG.md) · [简体中文](CHANGELOG.zh-CN.md)

## Unreleased

- Fix observed English sentences in the Chinese translation field with explicit target-language instructions and a two-sentence bilingual example.
- Expand real-model checks to 14 scenarios with empty/reused caches, preserving ambiguous times and explicitly stated AM/PM, complete sentences, negation and technical names; document remaining semantic errors.

## 0.1.0 — Initial source publication

- Local Apple Silicon MLX service and Chrome Manifest V3 extension for English/Japanese audio to Chinese/English captions.
- Selected-tab capture, original-audio playback, draggable fullscreen captions and local pairing.
- Optional drafts, Chinese-first translation, bounded queues, timestamp-gap handling and visible quality/overload metrics.
- Logic tests, isolated Chromium checks and explicit real-model smoke scripts.
- English/Simplified Chinese documentation, MIT code license, separate model-license notices and CI.

This is the initial source baseline, not a Chrome Web Store or PyPI release. Extension UI/runtime messages remain primarily Simplified Chinese. Windows/Linux/Intel inference and natural-speech accuracy benchmarks are not provided. The default Qwen 3B weights retain the separate Qwen Research License.
