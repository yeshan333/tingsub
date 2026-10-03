# Contributing to TingSub

[English](CONTRIBUTING.md) · [简体中文](CONTRIBUTING.zh-CN.md)

Thank you for helping make local bilingual captions more useful. English and Chinese issues and pull requests are welcome. Be respectful, discuss the work rather than the person, and do not publish anyone's private data.

## Before changing code

Search existing issues. For a bug, provide steps, expected/actual behavior, commit, machine and relevant settings. For a larger feature, new backend, permission change or dependency/model replacement, open an issue describing the user need and tradeoffs first. Security issues belong in [private reporting](SECURITY.md).

## Development workflow

1. Fork the repository and branch from `main`.
2. Follow the [development guide](docs/en/development.md) to install locked dependencies.
3. Keep a PR focused. Add regression coverage for changed behavior; tests must assert meaningful outcomes, not just non-empty output or implementation details.
4. Run the relevant Python, JavaScript, browser and documentation checks. State which were run and which require hardware/models you did not have.
5. Update both documentation languages and changelogs when user-visible behavior changes.
6. Open a PR with a concrete before/after description and verification evidence.

Logic fakes and protocol fixtures must be labeled as such. Never claim they measure model speed or accuracy. Real-model tests must fail when weights are missing or outputs violate assertions; they must not silently fall back to dummy output. Test names should state the condition and observable outcome without requiring readers to inspect implementation comments.

## Performance and quality contributions

Use identical input/settings for comparisons. Report first-text, first-Chinese and tail latency alongside sample counts, rejection/drop/error counts, model revisions and hardware. Follow [measurement guidance](docs/en/benchmarks.md). Do not improve apparent latency by silently dropping difficult speech. Share only audio/transcripts you are allowed to publish.

## Documentation translations

Keep `docs/en/` and `docs/zh-CN/` filenames and content coverage aligned, and link between counterpart pages. Root policies use `.zh-CN.md` counterparts. Commands, defaults, platform limits and license statements must agree. Run `python3 scripts/check_docs.py`. Proposals for additional languages are welcome; start with the README and installation guide, and label incomplete translations clearly.

## Review expectations

No secrets, model weights, `.local`, user recordings or browser profiles in commits. No unsupported accuracy or latency claims. Changes to the model license, network behavior, permissions or protocol must be explicit in the PR. CI must pass before normal merges; hardware-dependent results should be reported separately.

Contributions are licensed under the project's MIT code license. Only contribute material you have the right to share; third-party artifacts keep their own licenses. There is no CLA at present.
