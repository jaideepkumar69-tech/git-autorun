# Contributing

Thanks for helping improve git-autorun.

## Setup

Requires Python 3.10+ and git. There are no third-party dependencies.

```
git clone https://github.com/jaideepkumar69-tech/git-autorun.git
cd git-autorun
python test_auto_run.py
```

The tests are offline (no network, no LLM) and must pass on Linux and Windows; CI runs both.

## Guidelines

- Keep it a single dependency-free script; use the standard library only.
- Safety first: never weaken the URL allowlist, the allowed-files check on AI patches, or the "never overwrite/delete" behaviour. Add a test for any change touching them.
- Add or update tests in `test_auto_run.py` for behaviour changes.
- Match the existing style (type hints, short docstrings, logging via `Log.step`).
- Update `README.md` and add an entry under "Unreleased" in `CHANGELOG.md` for user-visible changes.
- Test risky changes inside a throwaway VM/container/WSL, since the tool runs untrusted code.

## Pull requests

1. Fork and create a branch from `main`.
2. Keep PRs focused; one change per PR.
3. Make sure `python test_auto_run.py` passes locally.
4. Describe what changed and why.

## Reporting issues

Use the issue templates. For security problems, follow [SECURITY.md](SECURITY.md) and do not open a public issue.

By contributing you agree your work is licensed under the [MIT License](LICENSE).
