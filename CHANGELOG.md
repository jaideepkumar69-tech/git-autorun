# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-01

### Added
- Clone a GitHub/GitLab repo (URL-validated, shallow, into a fresh timestamped folder), install dependencies, and run it.
- Dependency installation for Python (isolated `.venv`), npm, Cargo and Go.
- Run-command auto-detection (`npm run start|dev`, `main.py`/`app.py`/`run.py`, `cargo run`, `go run .`).
- Optional LLM auto-fix of failing runs via local Ollama or Anthropic, restricted to files named in the error output; originals kept as `*.orig`.
- `start.bat` generated in the installed project (activates `.venv`, runs the command); never overwrites a repo's own `start.bat` (writes `start.autorun.bat` instead).
- Monorepo support: project root is the first subfolder with a manifest (prefers `python`, `backend`, `server`, `app`, `src`).
- Import smoke test (`import <package>`) for Python libraries with no entry point.
- JSON-lines step log, `start.bat` wrapper for Windows, offline test suite, README, MIT license.
- GitHub Actions CI (Ubuntu and Windows, Python 3.10 and 3.13).

### Fixed
- Timeout output no longer crashes logging (bytes are decoded).
- A command still running at the timeout (e.g. a dev server) is treated as running, not as a failure that triggers AI patches.

[1.0.0]: https://github.com/jaideepkumar69-tech/git-autorun/releases/tag/v1.0.0
