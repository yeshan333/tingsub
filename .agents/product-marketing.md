# TingSub product marketing context

Version 1 · 2026-10-04

- Product: open-source local captions for English/Japanese browser audio on Apple Silicon. Chinese + English output, or Chinese + original. Translation is optional.
- Audience: Chinese-speaking viewers of foreign-language livestreams, talks and videos, especially when the player has no usable captions. Technically comfortable early adopters are the current installation audience.
- Problem: audio is hard to follow; existing subtitles may be missing. Users want captions without sending their audio to a cloud transcription provider.
- Differentiation: local MLX inference, a desktop model/download workspace and a user-controlled Chrome tab overlay. Do not claim unique features without comparative evidence.
- Primary conversion: download the macOS app or Chrome extension directly from public GitHub Release assets, without signing in. Installation guide and release notes remain visible. CI artifacts are a separate 30-day preview channel. App requires macOS 15+, includes its runtime, and is not Apple-notarized. No Chrome Web Store listing.
- Requirements: Apple Silicon, source macOS 14+, Chrome 116+, uv for source setup; 16 GB RAM recommended. Default model weights about 2.2 GB, plus dependencies/caches. Standalone builds have a separate OS minimum.
- Evidence: repository implementation and desktop screenshots. Screenshots use sample states. The homepage caption example is authored, not a live model demo. No customer metrics, testimonials, universal speed or accuracy claims.
- Privacy: inference runs locally; no audio upload, telemetry or automatic recording. Initial dependencies/models need internet; video websites make their own connections.
- Limits: overlapping voices, music and long sentences affect accuracy/latency. One active tab. No supported Windows/Linux/Intel/Firefox inference target.
- Licensing: code MIT; model licenses are separate. Default Qwen 2.5 3B weights use Qwen Research License.
- Voice: direct, calm, concrete. Warm paper, moss ink, useful product images. No invented social proof, urgency, superlatives or generic AI slogans.
- Languages: complete Simplified Chinese and English static pages; language switching stays within the product site.
- Guidance: coreyhaines31/marketingskills product-marketing, copywriting and cro, including copywriting/references/ai-tells.md. Actual product facts override generic marketing suggestions.
