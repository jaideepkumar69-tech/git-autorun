# Security Policy

## Threat model

git-autorun **intentionally executes code from repositories you point it at** (install scripts, build steps, the project itself). That is its purpose, not a vulnerability. Run it only in a disposable VM, container or WSL distro. Optional AI auto-fix sends error output and source files to the configured LLM provider (local Ollama by default if running, otherwise Anthropic).

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |
| < 1.0 | No |

## What counts as a vulnerability

In scope, for example:
- Bypassing the URL allowlist (`https://github.com|gitlab.com/<owner>/<repo>`) or injecting shell commands through the URL or `--run`
- AI patches written outside the allowed file set (path traversal) or outside the repo
- Overwriting or deleting files outside the workspace
- Leaking `ANTHROPIC_API_KEY` or other secrets into logs or generated files

Out of scope:
- Malicious behaviour of a repository you chose to run
- Running without a sandbox against your own advice above

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private reporting:
[Report a vulnerability](https://github.com/jaideepkumar69-tech/git-autorun/security/advisories/new)

Include the affected version, steps to reproduce, and the impact. You can expect an initial response within 7 days. Fixes are released as a patch version and credited in the changelog unless you prefer otherwise.
