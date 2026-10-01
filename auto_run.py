#!/usr/bin/env python3
"""git-autorun: clone a repo, install deps, run it, and let an LLM patch failures.

WARNING: this executes untrusted code from the internet on YOUR machine.
Run it inside a VM / container / WSL distro you can throw away.

Usage:
  python auto_run.py https://github.com/user/repo [--run "python main.py"]
                     [--workspace DIR] [--max-fixes 3] [--no-ai] [--yes]
Env:
  AUTORUN_PROVIDER    ollama|anthropic|none (default: local Ollama if running, else Anthropic)
  OLLAMA_MODEL        default: qwen3.8:latest   (any `ollama list` model, e.g. llama3)
  ANTHROPIC_API_KEY   only for the anthropic provider
  AUTORUN_MODEL       default: claude-sonnet-5-5
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

IS_WIN = platform.system() == "Windows"
URL_RE = re.compile(r"^https://(github\.com|gitlab\.com)/[\w.-]+/[\w.-]+?(\.git)?/?$")
MODEL = os.environ.get("AUTORUN_MODEL", "claude-sonnet-5-5")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.8:latest")
MAX_FILE_BYTES = 60_000
CMD_TIMEOUT = 600


# ---------------------------------------------------------------- logging
class Log:
    def __init__(self, path: Path):
        self.path = path

    def step(self, kind: str, **data):
        rec = {"t": time.strftime("%H:%M:%S"), "step": kind, **data}
        print(f"[{rec['t']}] {kind}: " + " ".join(f"{k}={str(v)[:200]!r}" for k, v in data.items()))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")


# ---------------------------------------------------------------- shell
@dataclass
class Result:
    code: int
    out: str
    err: str


class Shell:
    """Runs a command string via powershell.exe (Windows) or /bin/bash (else). No shell=True."""

    def __init__(self, cwd: Path, log: Log, env: dict | None = None):
        self.cwd, self.log, self.env = cwd, log, env or {}

    def argv(self, cmd: str) -> list[str]:
        if IS_WIN:
            return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd]
        return ["/bin/bash", "-lc", cmd]

    def run(self, cmd: str, timeout: int = CMD_TIMEOUT) -> Result:
        self.log.step("exec", cmd=cmd, cwd=str(self.cwd))
        try:
            p = subprocess.run(
                self.argv(cmd), cwd=self.cwd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout, env={**os.environ, **self.env},
            )
            r = Result(p.returncode, p.stdout, p.stderr)
        except subprocess.TimeoutExpired as e:
            dec = lambda b: b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or "")
            r = Result(124, dec(e.stdout), f"TIMEOUT after {timeout}s\n{dec(e.stderr)}")
        self.log.step("result", code=r.code, stderr_tail=r.err[-300:])
        return r


def git(args: list[str], cwd: Path | None = None) -> Result:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return Result(p.returncode, p.stdout, p.stderr)


# ---------------------------------------------------------------- setup
def clone(url: str, ws: Path, log: Log) -> Path:
    if not URL_RE.match(url):
        sys.exit("Refusing URL: only https://github.com|gitlab.com/<owner>/<repo> is accepted.")
    name = url.rstrip("/").removesuffix(".git").split("/")[-1]
    dest = ws / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}"  # never overwrite/delete anything
    log.step("clone", url=url, dest=dest)
    r = git(["clone", "--depth", "1", "--", url, str(dest)])
    if r.code:
        sys.exit(f"clone failed: {r.err}")
    return dest


def install(repo: Path, sh: Shell, log: Log) -> dict:
    """Install deps for every detected ecosystem. Python goes into an isolated .venv."""
    env: dict = {}
    has = lambda n: (repo / n).exists()
    if has("requirements.txt") or has("pyproject.toml") or has("setup.py"):
        venv = repo / ".venv"
        py = "python" if IS_WIN else "python3"
        sh.run(f'{py} -m venv "{venv}"')
        bindir = venv / ("Scripts" if IS_WIN else "bin")
        env["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        env["VIRTUAL_ENV"] = str(venv)
        sh.env = env
        if has("requirements.txt"):
            sh.run("python -m pip install -r requirements.txt")
        else:
            sh.run("python -m pip install -e .")
    if has("package.json"):
        sh.run("npm ci" if has("package-lock.json") else "npm install")
    if has("Cargo.toml"):
        sh.run("cargo build")
    if has("go.mod"):
        sh.run("go mod download")
    return env


def write_launcher(repo: Path, cmd: str, log: Log) -> Path | None:
    """Write start.bat into the cloned project (never overwrites the repo's own start.bat)."""
    if "\n" in cmd or "\r" in cmd:
        log.step("launcher_skip", reason="multi-line command")
        return None
    dest = repo / "start.bat"
    if dest.exists() and "git-autorun" not in dest.read_text(encoding="utf-8", errors="replace"):
        dest = repo / "start.autorun.bat"
    lines = ["@echo off", "rem Generated by git-autorun", "setlocal", 'cd /d "%~dp0"']
    if (repo / ".venv" / "Scripts" / "activate.bat").exists():
        lines.append('call ".venv\\Scripts\\activate.bat"')
    lines += ["call " + cmd.replace("%", "%%"), "set RC=%errorlevel%",
              "if not %RC%==0 echo Exited with code %RC%", "pause", "exit /b %RC%"]
    dest.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
    log.step("launcher", file=dest)
    return dest


MANIFESTS = ("requirements.txt", "pyproject.toml", "setup.py", "package.json", "Cargo.toml", "go.mod")


def find_project_root(repo: Path) -> Path:
    """Repo root if it has a manifest, else the first immediate subdir that does (monorepos)."""
    if any((repo / m).exists() for m in MANIFESTS):
        return repo
    pref = ("python", "backend", "server", "app", "src")
    subs = (p for p in repo.iterdir() if p.is_dir() and not p.name.startswith("."))
    for sub in sorted(subs, key=lambda p: (pref.index(p.name) if p.name in pref else len(pref), p.name)):
        if any((sub / m).exists() for m in MANIFESTS):
            return sub
    return repo


def smoke_import(repo: Path) -> str | None:
    """Library with no entry point: verify the top-level package imports."""
    if not any((repo / m).exists() for m in ("pyproject.toml", "setup.py")):
        return None
    for d in sorted(p for p in [repo, repo / "src"] if p.is_dir()):
        for p in sorted(d.iterdir()):
            if p.is_dir() and (p / "__init__.py").exists() and p.name.isidentifier() and not p.name.startswith(("test", "_")):
                return f'python -c "import {p.name}; print({p.name}.__name__, \'imported\')"'
    return None


def guess_run(repo: Path) -> str | None:
    pj = repo / "package.json"
    if pj.exists():
        try:
            scripts = json.loads(pj.read_text(encoding="utf-8")).get("scripts", {})
            for k in ("start", "dev"):
                if k in scripts:
                    return f"npm run {k}"
        except Exception:
            pass
    for f in ("main.py", "app.py", "run.py", "__main__.py"):
        if (repo / f).exists():
            return f"python {f}"
    if (repo / "Cargo.toml").exists():
        return "cargo run"
    if (repo / "go.mod").exists():
        return "go run ."
    return smoke_import(repo)


# ---------------------------------------------------------------- AI fix
def candidate_files(repo: Path, stderr: str) -> list[Path]:
    """Files named in the traceback / error output that live inside the repo, else entry points."""
    found: list[Path] = []
    root = repo.resolve()
    for m in re.finditer(r'(?:File "([^"]+)"|((?:[\w./\\:-]+)\.(?:py|js|ts|mjs|rs|go)):\d+)', stderr):
        raw = m.group(1) or m.group(2)
        p = Path(raw) if Path(raw).is_absolute() else repo / raw
        try:
            p = p.resolve()
            if p.is_file() and root in p.parents and ".venv" not in p.parts and "node_modules" not in p.parts:
                if p not in found:
                    found.append(p)
        except OSError:
            continue
    if not found:
        for f in ("main.py", "app.py", "index.js", "src/main.rs", "main.go"):
            if (repo / f).is_file():
                found.append((repo / f).resolve())
    return found[-3:]  # innermost frames matter most


def _post(url: str, body: dict, headers: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=2)
        return True
    except Exception:
        return False


def pick_provider() -> str | None:
    """AUTORUN_PROVIDER = ollama | anthropic | none; default: free local Ollama first, then Anthropic."""
    forced = os.environ.get("AUTORUN_PROVIDER")
    if forced:
        return None if forced == "none" else forced
    if _ollama_up():
        return "ollama"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def llm(prompt: str, provider: str) -> str:
    if provider == "ollama":  # free, local, no data leaves the machine
        r = _post(OLLAMA_URL + "/api/chat", {
            "model": OLLAMA_MODEL, "stream": False, "think": False, "format": "json",
            "options": {"num_ctx": 16384, "temperature": 0.1},
            "messages": [{"role": "user", "content": prompt}]}, {})
        return r["message"]["content"]
    key = os.environ["ANTHROPIC_API_KEY"]
    r = _post("https://api.anthropic.com/v1/messages",
              {"model": MODEL, "max_tokens": 8000, "messages": [{"role": "user", "content": prompt}]},
              {"x-api-key": key, "anthropic-version": "2023-06-01"}, 120)
    return "".join(b.get("text", "") for b in r["content"])


def ai_fix(repo: Path, cmd: str, res: Result, log: Log, provider: str) -> bool:
    files = candidate_files(repo, res.err + res.out)
    if not files:
        log.step("ai_skip", reason="no candidate source files")
        return False
    listing = "\n\n".join(
        f"=== {f.relative_to(repo.resolve()).as_posix()} ===\n{f.read_text(encoding='utf-8', errors='replace')[:MAX_FILE_BYTES]}"
        for f in files)
    prompt = (
        f"A project run failed.\nCommand: {cmd}\nExit code: {res.code}\n\n"
        f"STDERR (tail):\n{res.err[-4000:]}\n\nSTDOUT (tail):\n{res.out[-1500:]}\n\n"
        f"Source files:\n{listing}\n\n"
        "Fix the root cause with the smallest change. Reply with ONLY JSON: "
        '{"file": "<relative path from the list above>", "content": "<full corrected file>", "why": "<one line>"}. '
        "Do not change files outside the list. Do not add network calls or shell execution."
    )
    try:
        text = llm(prompt, provider)
        m = re.search(r"\{.*\}", text, re.S)
        patch = json.loads(m.group(0))
        target = (repo / patch["file"]).resolve()
        allowed = {f for f in files}
        if target not in allowed:  # blocks path traversal and edits to unlisted files
            log.step("ai_reject", reason="file not in allowed set", file=patch["file"])
            return False
        shutil.copy2(target, target.with_suffix(target.suffix + ".orig"))
        target.write_text(patch["content"], encoding="utf-8", newline="\n")
        log.step("ai_patch", file=patch["file"], why=patch.get("why", ""))
        return True
    except Exception as e:
        log.step("ai_error", error=repr(e))
        return False


def run_with_fixes(repo: Path, sh: Shell, cmd: str, max_fixes: int, provider: str | None, log: Log) -> bool:
    for attempt in range(max_fixes + 1):
        res = sh.run(cmd)
        if res.code in (0, 124):  # 124 = still running at timeout (server/long job), not a crash
            log.step("success" if res.code == 0 else "running_at_timeout", attempt=attempt)
            print(res.out[-2000:])
            return True
        if not provider or attempt == max_fixes:
            break
        if not ai_fix(repo, cmd, res, log, provider):
            break
    log.step("failed", attempts=attempt + 1)
    return False


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--run", help="command to run (auto-detected if omitted)")
    ap.add_argument("--workspace", default=str(Path.home() / "autorun-workspace"))
    ap.add_argument("--max-fixes", type=int, default=3)
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the execute-untrusted-code confirmation")
    a = ap.parse_args()

    ws = Path(a.workspace)
    ws.mkdir(parents=True, exist_ok=True)
    log = Log(ws / "autorun.log.jsonl")

    if not a.yes:
        print("This will run install scripts and code from the repo on THIS machine.")
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            return 2

    repo = clone(a.url, ws, log)
    root = find_project_root(repo)
    if root != repo:
        log.step("project_root", path=root)
    repo = root
    sh = Shell(repo, log)
    install(repo, sh, log)
    cmd = a.run or guess_run(repo)
    if not cmd:
        log.step("no_run_command", hint="pass --run")
        return 3
    if os.name == "nt" or IS_WIN:
        write_launcher(repo, cmd, log)
    ok = run_with_fixes(repo, sh, cmd, a.max_fixes, None if a.no_ai else pick_provider(), log)
    print(f"\nRepo: {repo}\nLog:  {log.path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
