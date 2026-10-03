# Security policy

[English](SECURITY.md) · [简体中文](SECURITY.zh-CN.md)

## Supported versions

TingSub is early-stage software. Security fixes target the latest `main` and will be noted in the changelog. Older commits and forks are not maintained as separate security branches. There is no guaranteed response-time SLA.

## Report a vulnerability

Use GitHub's [private vulnerability reporting](https://github.com/yeshan333/tingsub/security/advisories/new). Include the affected commit, impact, prerequisites, minimal reproduction and suggested mitigation. Use synthetic examples; never include real pairing codes, private recordings or another user's data.

If the private report form is unavailable, open an issue asking the maintainer for a private reporting channel **without exploit details or sensitive attachments**. Do not post a working exploit in a public issue before coordinated disclosure.

## Security boundaries

The service is designed for a single trusted local user. It binds to loopback, checks the extension origin, authenticates WebSocket sessions with a local secret and limits active inference to one stream. `/health` is intentionally unauthenticated and returns readiness metadata only. This is not a hardened multi-user or remote inference server. Do not expose it over a public interface, tunnel or reverse proxy.

The overlay is part of the video page and its displayed text can be read by that page. Local malware or code running under the same OS account is outside the pairing boundary. Models can produce incorrect or malicious-looking text; caption text must remain plain text, never executable HTML. See [privacy and permissions](docs/en/privacy.md).

Rotate a leaked pairing code using the steps in the privacy guide. Review model/dependency licenses and sources before replacing them. Private model paths, logs and benchmark outputs must not be committed.
