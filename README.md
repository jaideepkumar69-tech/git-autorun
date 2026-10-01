# git-autorun

[![tests](https://github.com/jaideepkumar69-tech/git-autorun/actions/workflows/tests.yml/badge.svg)](https://github.com/jaideepkumar69-tech/git-autorun/actions/workflows/tests.yml)
Clone a GitHub/GitLab repo, install its dependencies, run it, and (optionally) let an LLM patch failures.
It also writes a `start.bat` into the installed project so you can relaunch it with a double-click.

> **Warning:** this executes untrusted code from the internet on your machine.
> Run it inside a VM, container or WSL distro you can throw away.

## Requirements

- Python 3.10+ and git on `PATH`
- Optional, for AI fixes: a local [Ollama](https://ollama.com) or an `ANTHROPIC_API_KEY`
- Optional, per project: `npm`, `cargo`, `go`

No third-party Python packages are needed.

## Usage

```
python auto_run.py https://github.com/user/repo [--run "python main.py"]
                   [--workspace DIR] [--max-fixes 3] [--no-ai] [--yes]
```

Or on Windows, use the wrapper (prompts for the URL if none is given):

```
start.bat https://github.com/user/repo ["run command"]
start.bat test
```

| Flag | Meaning |
| --- | --- |
| `--run CMD` | Command to run (auto-detected if omitted) |
| `--workspace DIR` | Where repos are cloned (default `~/autorun-workspace`) |
| `--max-fixes N` | Max AI repair attempts (default 3) |
| `--no-ai` | Never call an LLM |
| `--yes` | Skip the "run untrusted code" confirmation |

## What it does

1. Validates the URL (only `https://github.com|gitlab.com/<owner>/<repo>`) and shallow-clones into a fresh timestamped folder. Nothing is overwritten.
2. Finds the project root: the repo root, or for monorepos the first subfolder with a manifest (prefers `python`, `backend`, `server`, `app`, `src`).
3. Installs dependencies: Python into an isolated `.venv` (`requirements.txt`, `pyproject.toml` or `setup.py`), plus `npm ci`/`npm install`, `cargo build`, `go mod download`.
4. Picks a run command: `npm run start|dev`, `main.py`/`app.py`/`run.py`, `cargo run`, `go run .`; for libraries with no entry point it smoke-tests `import <package>`.
5. Writes **`start.bat`** into the project (activates `.venv`, runs the command, shows the exit code). If the repo already has its own `start.bat`, yours is written as `start.autorun.bat` instead.
6. Runs the command. On failure, an LLM may patch one of the files named in the traceback (originals are kept as `*.orig`), then it retries.

A JSON-lines log of every step is written to `<workspace>/autorun.log.jsonl`.

## AI providers

`AUTORUN_PROVIDER=ollama|anthropic|none` (default: local Ollama if running, else Anthropic if `ANTHROPIC_API_KEY` is set).

| Variable | Default |
| --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `qwen3.8:latest` |
| `AUTORUN_MODEL` | `claude-sonnet-5-5` |
| `ANTHROPIC_API_KEY` | needed only for the anthropic provider |

AI patches are restricted to files listed in the error output, inside the repo.

## Tests

```
python test_auto_run.py
```

Offline: no network, no LLM.

## License

[MIT](LICENSE)
