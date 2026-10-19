"""Dispatch tool for the CoevoDB migration (orchestrator side).

The orchestrator (PI) hands each work package to a headless executor, ``grok``
or ``codex``, that works in its own git worktree on branch ``grok/<pkg>`` (the
prefix is kept for codex packages: CLAUDE.md names it):

    python tools/orch/grok_worker.py spawn    <pkg> --base <tag|branch> [--executor codex|grok]
    python tools/orch/grok_worker.py status   <pkg> [--wait]
    python tools/orch/grok_worker.py review   <pkg>
    python tools/orch/grok_worker.py resume   <pkg> <feedback.md>
    python tools/orch/grok_worker.py handover <pkg> [--executor codex|grok]
    python tools/orch/grok_worker.py merge    <pkg> --into <branch>
    python tools/orch/grok_worker.py cleanup  <pkg> [--abandon]
    python tools/orch/grok_worker.py list

Layout, all under the main checkout (``.orch/`` and ``.worktrees/`` are
git-ignored):

    .orch/briefs/<pkg>.md           brief written by the orchestrator (input)
    .orch/logs/<pkg>.jsonl          executor JSON events (grok streaming-json,
                                    codex exec --json), runs appended
    .orch/logs/<pkg>.stderr.log     executor stderr
    .orch/state/<pkg>.json          package state (written by this CLI only)
    .orch/state/<pkg>.run<N>.json   one record per executor run (supervisor-owned)
    .orch/reviews/<pkg>.md          review package
    .worktrees/<pkg>/               worktree on branch grok/<pkg>
    .worktrees/<pkg>/.orch/         brief.md, report.md, review-<n>.md, tmp/
    .worktrees/<pkg>/.codex/rules/  execpolicy rules for a codex executor

Environment overrides: ``ORCH_GROK_CMD`` / ``ORCH_CODEX_CMD`` (path to the
binary, or a JSON list used as the command prefix), ``ORCH_EXECUTOR`` (default
executor for ``spawn`` and ``handover``), ``ORCH_COMMIT_TRAILER`` (appended to
the commits ``merge`` creates), ``ORCH_ROOT`` (main checkout, normally derived).

Standard library only. The flow and the review checklist this tool serves are
in framework/surprise/docs/ORCHESTRATION.md.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import locale
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

SCRIPT = Path(__file__).resolve()

BRANCH_PREFIX = "grok/"
EXECUTORS = ("grok", "codex")
# User's decision (2026-10-19, S15): codex stands in for grok for now; grok's
# usage balance ran out mid-package. `--executor grok` switches back.
DEFAULT_EXECUTOR = os.environ.get("ORCH_EXECUTOR", "codex")
# The user's command line: codex -m gpt-6.1-sol -c 'model_reasoning_effort="high"' --yolo
CODEX_MODEL = "gpt-6.1-sol"
CODEX_CONFIG = (
    'model_reasoning_effort="high"',
    # codex reads AGENTS.md; the repo root has only CLAUDE.md (executor mode)
    'project_doc_fallback_filenames=["CLAUDE.md"]',
)
CODEX_RULES = ".codex/rules/orch.rules"
DEFAULT_TIMEOUT_MIN = 60
DEFAULT_MAX_PARALLEL = 2
DEFAULT_MAX_REWORK = 2
DEFAULT_TEST_TIMEOUT_MIN = 30

# Never visible to the executor or to the code it wrote (review re-runs).
# The one exception (user's decision, S9, 2026-10-15): a package spawned with
# `--llm-key N` gets the key in its executor process, plus LLM_CAP_ENV = N, the
# ceiling on real calls that the S9 gateway honours. Review re-runs never get it.
STRIP_ENV = ("DEEPSEEK_API_KEY",)
LLM_CAP_ENV = "SURPRISE_LLM_MAX_CALLS"

ROLE_LINE = "角色：执行者"
SPAWN_PROMPT = "读 .orch/brief.md，按其中说明完成工作包"
RESUME_PROMPT = (
    "读 .orch/{name} 里的审查意见并按意见返工；范围、禁区与报告格式仍以 "
    ".orch/brief.md 为准，做完后提交并更新 .orch/report.md"
)
HANDOVER_PROMPT = (
    "读 .orch/brief.md，按其中说明完成工作包。这个 worktree 里已有上一位执行者"
    "中途退出时留下的改动（用 git status 与 git diff 查看）：先读懂它们，能用的接着用，"
    "不对的改掉，然后完成工作包，照说明提交并写 .orch/report.md"
)

PKG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SESSION_RE = re.compile(r"^(s\d{2}[a-z]?)(?:-|$)")

# Tracked paths the executor may never change: denied to grok's edit tools and
# flagged as out of bounds by `review`.
PROTECTED = (
    "framework/surprise/gates/",
    "framework/surprise/docs/",
    "CLAUDE.md",
    ".grok/",
    ".codex/",
    "tools/orch/",
)
# Orchestrator-side bookkeeping (untracked): denied to grok's edit tools only.
ORCH_PRIVATE = (".orch/briefs/", ".orch/state/", ".orch/reviews/", ".orch/logs/")
# Paths frozen once the given tag exists (CLAUDE.md: harness freezes after S4).
FROZEN_AFTER = {"s04-done": ("framework/surprise/harness/",)}

# Shell commands the executor must never run. grok matches a `Bash(...)` rule
# against every chained segment, as a literal prefix or as a glob in which `*`
# also matches spaces; matching is case-sensitive. Native Windows has no
# sandbox, so the three shell families grok may use are all covered.
DENY_BASH = [
    # git: no publishing, no history rewriting, no touching other refs
    "git push*", "git tag*", "git merge *", "git rebase*",
    "git reset *--hard*", "git worktree*",
    "git branch *-D*", "git branch *--delete*",
    # the same behind global options (git -C <dir> ..., git -c k=v ...)
    "git -* push", "git -* push *", "git -* tag", "git -* tag *",
    "git -* merge *", "git -* rebase", "git -* rebase *",
    "git -* reset *--hard*", "git -* worktree *",
    "git -* branch *-D*", "git -* branch *--delete*",
    # recursive deletes, POSIX shell
    "rm -rf*", "rm -fr*", "rm -Rf*", "rm -fR*", "rm -r *", "rm -R *",
    "rm -r -f*", "rm -f -r*", "rm --recursive*",
    # recursive deletes, cmd.exe
    "rd /s*", "rd /S*", "rd /q /s*", "rd /Q /S*",
    "rmdir /s*", "rmdir /S*", "rmdir /q /s*", "rmdir /Q /S*",
    "del /s*", "del /S*",
    # executors never log in to the experiment server (ORCHESTRATION §12)
    "ssh*", "scp*", "rsync*", "sftp*",
]
# recursive deletes, PowerShell (cmdlet and its aliases)
DENY_BASH += [
    f"{name} {flag}"
    for name in ("Remove-Item", "remove-item", "rm", "ri", "del", "erase",
                 "rd", "rmdir")
    for flag in ("*-Recurse*", "*-recurse*", "* -r", "* -r *")
]

# The same for codex: execpolicy prefix rules, which codex honours under --yolo
# (probe, codex-cli 0.163.0). A rule matches leading tokens only (a list is a
# set of alternatives), so flags later in the command are not caught and
# `git -C`/`git -c` are refused outright. Codex has no rule for its own file
# edits: protected paths rest on `review` alone.
CODEX_FORBIDDEN = [
    (["git", ["push", "tag", "merge", "rebase", "worktree"]],
     "publishing, tags and merges are the orchestrator's"),
    (["git", "reset", "--hard"], "no history rewriting"),
    (["git", "branch", ["-D", "-d", "--delete"]], "no deleting branches"),
    (["git", ["-C", "-c", "--git-dir", "--work-tree"]],
     "run git in the worktree, without global options"),
    (["rm", ["-rf", "-fr", "-Rf", "-fR", "-r", "-R", "--recursive"]], "no recursive deletes"),
    ([["rd", "rmdir"], ["/s", "/S", "/q", "/Q"]], "no recursive deletes"),
    ([["del", "erase"], ["/s", "/S"]], "no recursive deletes"),
    ([["Remove-Item", "remove-item", "rm", "ri", "del", "erase", "rd", "rmdir"],
      ["-Recurse", "-recurse", "-r", "-R"]], "no recursive deletes"),
    ([["ssh", "ssh.exe", "scp", "scp.exe", "rsync", "rsync.exe", "sftp", "sftp.exe"]],
     "executors never log in to the experiment server"),
]

SKIP_RE = re.compile(
    r"pytest\.mark\.(?:skip|skipif|xfail)|pytest\.(?:skip|xfail|importorskip)\s*\("
    r"|unittest\.skip|\.skipTest\s*\(|\bSkipTest\b|collect_ignore|--deselect"
    r"|-k\s+['\"]?not\b"
)
ASSERT_RE = re.compile(
    r"^\s*assert\b|\bself\.assert\w+\s*\(|\bpytest\.(?:raises|approx|warns)\s*\("
    r"|\.assert_(?:called|not_called|any_call|has_calls)\w*\s*\("
)
BROAD_EXCEPT_RE = re.compile(
    r"^\s*except\s*:|^\s*except\s+\(?\s*(?:Base)?Exception\b"
    r"|\bsuppress\s*\(\s*(?:Base)?Exception\b"
)
TEST_PATH_RE = re.compile(
    r"(?:^|/)(?:tests?|testing)/|(?:^|/)test_[^/]*\.py$|_test\.py$"
    r"|(?:^|/)conftest\.py$|/gates/"
)
TEST_CONFIG_NAMES = {"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg",
                     "tox.ini", ".coveragerc"}
SECRET_FILE_RE = re.compile(
    r"(?:^|/)(?:\.env(?:\.[^/]*)?|secrets\.env|api-keys\.ya?ml|id_rsa|[^/]*\.pem)$"
)
SECRET_RES = [
    ("key-like token", re.compile(r"\b(?:sk|xai)-[A-Za-z0-9_\-]{20,}")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("DEEPSEEK_API_KEY literal", re.compile(
        r"DEEPSEEK_API_KEY['\"]?\s*[:=]\s*['\"]?(?!\$\{|os\.|None\b)[A-Za-z0-9_\-]{12,}")),
    ("bearer token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}")),
    ("secret assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|passwd|password)\b['\"]?\s*[:=]\s*"
        r"['\"][A-Za-z0-9+/_\-]{20,}['\"]")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
ALLOW_BLOCK_RE = re.compile(r"```allow-paths[ \t]*\r?\n(.*?)```", re.S)
PYTEST_COUNT_RE = re.compile(
    r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?|deselected)")


class OrchError(Exception):
    """A precondition failed; the message is shown and the exit code is 1."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode(locale.getpreferredencoding(False), errors="replace")


def _find_root() -> Path:
    override = os.environ.get("ORCH_ROOT")
    if override:
        return Path(override).resolve()
    proc = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=str(SCRIPT.parent), capture_output=True)
    if proc.returncode != 0:
        sys.exit("grok_worker: not inside a git repository")
    return Path(_decode(proc.stdout).strip()).parent


ROOT = _find_root()
ORCH = ROOT / ".orch"
WORKTREES = ROOT / ".worktrees"
ARCHIVE = ROOT / "framework" / "surprise" / "docs" / "orch"


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                          cwd=str(cwd or ROOT), capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    if check and proc.returncode != 0:
        detail = (_decode(proc.stderr) or out).strip()
        raise OrchError(f"git {' '.join(args)}: {detail}")
    return out


def git_ok(*args: str, cwd: Path | None = None) -> bool:
    return subprocess.run(["git", *args], cwd=str(cwd or ROOT),
                          capture_output=True).returncode == 0


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{secs:02d}s"


def rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def check_pkg(pkg: str) -> str:
    if not PKG_RE.match(pkg):
        raise OrchError(f"bad package id {pkg!r}: use lowercase letters, digits, . _ -")
    return pkg


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # a reader has it open (Windows)
            if attempt == 19:
                raise
            time.sleep(0.05)


def state_path(pkg: str) -> Path:
    return ORCH / "state" / f"{pkg}.json"


def run_path(pkg: str, n: int) -> Path:
    return ORCH / "state" / f"{pkg}.run{n}.json"


def load_state(pkg: str) -> dict:
    state = _read_json(state_path(pkg))
    if state is None:
        raise OrchError(f"unknown package {pkg!r}: no {rel(state_path(pkg))}")
    return state


def save_state(state: dict) -> None:
    _write_json(state_path(state["pkg"]), state)


def all_packages() -> list[str]:
    folder = ORCH / "state"
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.json") if ".run" not in p.stem)


def path_matcher(pattern: str) -> re.Pattern[str]:
    """Compile a repo-relative glob: `*` stays inside one path component, `**`
    crosses components, and a directory matches everything below it."""
    pattern = pattern.strip().replace("\\", "/").removeprefix("./").rstrip("/")
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"(?:/.*)?\Z")


def matches_any(path: str, patterns) -> bool:
    return any(path_matcher(p).match(path) for p in patterns)


def allow_paths_from_brief(text: str) -> list[str]:
    patterns = []
    for block in ALLOW_BLOCK_RE.findall(text):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def session_of(pkg: str) -> str | None:
    match = SESSION_RE.match(pkg)
    return match.group(1) if match else None


# --------------------------------------------------------------------------
# processes
# --------------------------------------------------------------------------

def _kernel32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE,
                                       ctypes.POINTER(wintypes.DWORD))
    k32.GetProcessTimes.argtypes = (
        wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k32


def proc_token(pid: int | None) -> str | None:
    """Creation-time stamp of a live process, None when it is not running.
    Compared against the stamp taken at launch so a reused PID is not mistaken
    for our process."""
    if not pid:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = _kernel32()
        handle = k32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            if code.value != 259:  # STILL_ACTIVE
                return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return "unknown"
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    try:
        fields = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19]
    except (OSError, IndexError):
        return "unknown"


def alive(pid: int | None, token: str | None) -> bool:
    current = proc_token(pid)
    if current is None:
        return False
    return token in (None, "unknown") or current in ("unknown", token)


def kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    time.sleep(3)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _own_group() -> dict:
    """Popen kwargs that give the child its own process group."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def child_env(worktree: Path | None = None) -> tuple[dict, list[str]]:
    """Environment for executor-side processes: secrets removed; with a
    worktree, also a temp directory inside it (parallel packages must not
    collide) and this interpreter first on PATH, so the executor's `python` /
    `pytest` are the ones `review` re-runs with."""
    env, stripped = {}, []
    for key, value in os.environ.items():
        if key.upper() in STRIP_ENV:
            stripped.append(key.upper())
        else:
            env[key] = value
    if worktree is not None:
        tmp = worktree / ".orch" / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        for name in ("TMP", "TEMP", "TMPDIR"):
            env[name] = str(tmp)
        home = Path(sys.executable).parent
        dirs = [str(d) for d in (home, home / "Scripts", home / "bin") if d.is_dir()]
        path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
        env[path_key] = os.pathsep.join([*dirs, env.get(path_key, "")])
        if sys.prefix != sys.base_prefix:
            env["VIRTUAL_ENV"] = sys.prefix
    return env, stripped


def executor_of(state: dict) -> str:
    return state.get("executor", "grok")  # packages from before codex were grok's


def executor_cmd(executor: str) -> list[str]:
    name = f"ORCH_{executor.upper()}_CMD"
    raw = os.environ.get(name, "").strip()
    if raw:
        return [str(part) for part in json.loads(raw)] if raw.startswith("[") else [raw]
    exe = shutil.which(executor)
    if not exe:
        raise OrchError(f"{executor} not found on PATH (or set {name})")
    return [exe]


def executor_version(executor: str) -> tuple[list[str], str]:
    cmd = executor_cmd(executor)
    proc = subprocess.run([*cmd, "--version"], capture_output=True)
    if proc.returncode != 0:
        maker = "xAI's grok" if executor == "grok" else "OpenAI's codex CLI"
        raise OrchError(f"{cmd[0]} --version failed; is this {maker}?")
    return cmd, _decode(proc.stdout).strip()


def deny_rules() -> list[str]:
    rules = [f"Bash({pattern})" for pattern in DENY_BASH]
    for path in (*PROTECTED, *ORCH_PRIVATE):
        glob = path + "**" if path.endswith("/") else path
        for tool in ("Edit", "Write"):
            # the bare form is joined with the session cwd; the **/ form also
            # covers absolute paths into the main checkout and other worktrees
            rules.append(f"{tool}({glob})")
            rules.append(f"{tool}(**/{glob})")
    return rules


def executor_argv(state: dict, prompt: str, *, resume: bool) -> list[str]:
    # auto-approve is only ever granted inside a package worktree
    executor = executor_of(state)
    if Path(state["worktree"]).resolve().parent != WORKTREES.resolve():
        raise OrchError(f"refusing to run {executor} outside {rel(WORKTREES)}/: "
                        f"{state['worktree']}")
    if executor == "codex":
        return codex_argv(state, prompt, resume=resume)
    return grok_argv(state, prompt, resume=resume)


def codex_argv(state: dict, prompt: str, *, resume: bool) -> list[str]:
    argv = [*executor_cmd("codex"), "exec", *(["resume"] if resume else []), "--json",
            # = --yolo: no approvals, no sandbox; the execpolicy rules still apply
            "--dangerously-bypass-approvals-and-sandbox"]
    if not resume:  # resume has no --cd; the run's cwd is the worktree either way
        argv += ["--cd", state["worktree"]]
    argv += ["-m", state.get("model") or CODEX_MODEL]
    for item in CODEX_CONFIG:
        argv += ["-c", item]
    if state.get("llm_max_calls") is not None:
        # codex drops *KEY*/*SECRET*/*TOKEN* variables from the shells it starts
        argv += ["-c", "shell_environment_policy.ignore_default_excludes=true"]
    if resume:
        argv.append(state["session_id"])
    argv.append(prompt)
    return argv


def codex_rules_text() -> str:
    lines = ["# Written by tools/orch/grok_worker.py; the executor must not change it."]
    for pattern, why in CODEX_FORBIDDEN:
        lines.append(f"prefix_rule(pattern = {json.dumps(pattern)}, "
                     f"decision = \"forbidden\", justification = {json.dumps(why)})")
    return "\n".join(lines) + "\n"


def install_codex_rules(state: dict) -> None:
    """(Re)write the worktree's execpolicy rules and check codex parses them.
    A file that differs from ours before a run is recorded for `review`."""
    path = Path(state["worktree"]) / CODEX_RULES
    text = codex_rules_text()
    if path.is_file() and path.read_text(encoding="utf-8", errors="replace") != text:
        state.setdefault("rules_changed", []).append(now_iso())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    proc = subprocess.run([*executor_cmd("codex"), "execpolicy", "check", "--rules",
                           str(path), "--", "git", "push"], capture_output=True)
    if '"decision":"forbidden"' not in _decode(proc.stdout).replace(" ", ""):
        raise OrchError(f"codex does not refuse `git push` under {rel(path)}: "
                        f"{_decode(proc.stdout + proc.stderr).strip()[:300]}")


def session_id(state: dict) -> str | None:
    """grok's id is chosen at launch; codex reports its thread id in the log,
    so a codex session is the thread of the latest run that did not resume."""
    if state.get("session_id"):
        return state["session_id"]
    threads, run = {}, None
    for event in read_events(Path(state["log"])):
        if event.get("type") == "orch.start":
            run = event.get("run")
        elif event.get("type") == "thread.started" and run is not None:
            threads.setdefault(run, event.get("thread_id"))
    for entry in reversed(state.get("runs") or []):
        if entry["kind"] != "resume":
            return threads.get(entry["n"])
    return None


def grok_argv(state: dict, prompt: str, *, resume: bool) -> list[str]:
    argv = [*executor_cmd("grok"), "--no-auto-update", "--always-approve"]
    if state.get("trust", True):
        # a worktree is its own workspace for grok's folder trust; without
        # this, CLAUDE.md and project config are not loaded in headless mode
        argv.append("--trust")
    argv += ["--cwd", state["worktree"]]
    # --session-id only creates (and must be a UUID); continuing needs --resume
    argv += ["--resume" if resume else "--session-id", state["session_id"]]
    argv += ["--output-format", "streaming-json"]
    if state.get("model"):
        argv += ["--model", state["model"]]
    for rule in deny_rules():
        argv += ["--deny", rule]
    argv += ["-p", prompt]
    return argv


# --------------------------------------------------------------------------
# runs: supervisor, launch, status
# --------------------------------------------------------------------------

def _marker(handle, event: dict) -> None:
    handle.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
    handle.flush()


def supervise(pkg: str, n: int) -> int:
    """Run the executor for one run of a package, enforce the timeout, record
    the exit. Owns .orch/state/<pkg>.run<N>.json (the executor's pid is kept
    under the grok_* keys, so records from before codex still read)."""
    state = load_state(pkg)
    run = state["runs"][n - 1]
    worktree = Path(state["worktree"])
    env, _ = child_env(worktree)
    executor = run.get("executor", "grok")
    if executor == "grok":
        env["GROK_DISABLE_AUTOUPDATER"] = "1"
    cap = state.get("llm_max_calls")
    if cap is not None:
        key = llm_key()
        if key:
            env["DEEPSEEK_API_KEY"] = key
        env[LLM_CAP_ENV] = str(cap)
    record = {
        "pkg": pkg, "run": n, "kind": run["kind"],
        "supervisor_pid": os.getpid(), "supervisor_token": proc_token(os.getpid()),
        "started_at": now_iso(), "started_ts": time.time(),
        "timeout_min": run["timeout_min"],
    }
    log_path, err_path = Path(state["log"]), Path(state["stderr_log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timed_out, code, error = False, None, None
    with open(log_path, "ab") as log, open(err_path, "ab") as err:
        _marker(log, {
            "type": "orch.start", "pkg": pkg, "run": n, "kind": run["kind"],
            "executor": executor, "at": record["started_at"],
            "sessionId": state.get("session_id"),
            "envStripped": list(STRIP_ENV),
            "wasSetInParent": bool(run.get("key_was_set")),
            "childEnvHas": {k: any(e.upper() == k for e in env) for k in STRIP_ENV},
            "llmMaxCalls": cap,
        })
        try:
            proc = subprocess.Popen(
                run["argv"], cwd=str(worktree), env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=err, **_own_group())
        except OSError as exc:
            error = f"could not start {executor}: {exc}"
        else:
            record.update(grok_pid=proc.pid, grok_token=proc_token(proc.pid))
            _write_json(run_path(pkg, n), record)
            try:
                code = proc.wait(timeout=run["timeout_min"] * 60)
            except subprocess.TimeoutExpired:
                timed_out = True
                kill_tree(proc.pid)
                try:
                    code = proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    code = None
        _marker(log, {"type": "orch.exit", "pkg": pkg, "run": n, "at": now_iso(),
                      "exitCode": code, "timedOut": timed_out, "error": error})
    record.update(ended_at=now_iso(), ended_ts=time.time(), exit_code=code,
                  timed_out=timed_out, error=error)
    _write_json(run_path(pkg, n), record)
    return 0 if code == 0 and not timed_out else 2


def start_run(state: dict, kind: str, prompt: str, timeout_min: float,
              detach: bool) -> int:
    """Blocks until the executor exits (run it as a background task of the
    calling session) unless `detach` is set."""
    pkg = state["pkg"]
    n = len(state["runs"]) + 1
    _, stripped = child_env()
    argv = executor_argv(state, prompt, resume=(kind == "resume"))
    if executor_of(state) == "codex":
        install_codex_rules(state)
    state["runs"].append({
        "n": n, "kind": kind, "executor": executor_of(state),
        "requested_at": now_iso(), "requested_ts": time.time(),
        "timeout_min": timeout_min, "prompt": prompt, "key_was_set": bool(stripped),
        "argv": argv,
    })
    save_state(state)
    if not detach:
        print(f"running   run {n} ({kind}) in the foreground, timeout "
              f"{timeout_min:g}m; watch it with `status {pkg}`", flush=True)
        code = supervise(pkg, n)
        print_status(state, run_status(state), 8)
        return code

    env, _ = child_env()
    env["ORCH_ROOT"] = str(ROOT)
    cmd = [sys.executable, str(SCRIPT), "_supervise", pkg, str(n)]
    sup_log = ORCH / "logs" / f"{pkg}.supervisor.log"
    sup_log.parent.mkdir(parents=True, exist_ok=True)
    with open(sup_log, "ab") as err:
        kwargs = dict(cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                      stdout=subprocess.DEVNULL, stderr=err)
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            try:  # leave the caller's job object so we outlive the calling shell
                subprocess.Popen(cmd, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                                 **kwargs)
            except OSError:
                subprocess.Popen(cmd, creationflags=flags, **kwargs)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kwargs)

    deadline = time.time() + 20
    while time.time() < deadline:
        record = _read_json(run_path(pkg, n))
        if record and (record.get("grok_pid") or record.get("ended_at")):
            break
        time.sleep(0.2)
    info = run_status(state)
    if info["phase"] == "running":
        print(f"started   run {n} ({kind}), {executor_of(state)} pid "
              f"{info['record'].get('grok_pid')}")
    else:
        print(f"WARNING   run {n} is '{info['phase']}' right after launch; "
              f"see {rel(sup_log)} and {rel(state['stderr_log'])}")
    return 0


def run_status(state: dict) -> dict:
    """phase: none | starting | running | finished | lost"""
    runs = state.get("runs") or []
    if not runs:
        return {"phase": "none", "n": 0, "run": None, "record": {}, "elapsed": 0.0}
    run = runs[-1]
    record = _read_json(run_path(state["pkg"], run["n"])) or {}
    start = record.get("started_ts") or run["requested_ts"]
    info = {"n": run["n"], "run": run, "record": record}
    if record.get("ended_at"):
        info.update(phase="finished", elapsed=record["ended_ts"] - start)
    elif alive(record.get("grok_pid"), record.get("grok_token")) or alive(
            record.get("supervisor_pid"), record.get("supervisor_token")):
        info.update(phase="running", elapsed=time.time() - start)
    elif not record and time.time() - run["requested_ts"] < 30:
        info.update(phase="starting", elapsed=time.time() - start)
    else:
        info.update(phase="lost", elapsed=0.0)
    return info


def stop_run(state: dict, info: dict, reason: str) -> None:
    """Kill a running grok and make sure the run record gets closed."""
    record = info["record"]
    if record.get("grok_pid") and alive(record["grok_pid"], record.get("grok_token")):
        kill_tree(record["grok_pid"])
    path = run_path(state["pkg"], info["n"])
    deadline = time.time() + 40
    while time.time() < deadline:  # the supervisor normally writes the ending
        if (_read_json(path) or {}).get("ended_at"):
            break
        if not alive(record.get("supervisor_pid"), record.get("supervisor_token")):
            break
        time.sleep(0.5)
    record = _read_json(path) or record
    if not record.get("ended_at"):
        record.update(ended_at=now_iso(), ended_ts=time.time(), exit_code=None)
    record.update(stopped_by=reason, timed_out=record.get("timed_out")
                  or reason == "timeout")
    _write_json(path, record)


def is_running(pkg: str) -> bool:
    state = _read_json(state_path(pkg))
    if not state or state.get("cleaned_at"):
        return False
    return run_status(state)["phase"] in ("running", "starting")


# --------------------------------------------------------------------------
# log reading
# --------------------------------------------------------------------------

def read_events(path: Path) -> list[dict]:
    events = []
    try:
        handle = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return events
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            events.append(event if isinstance(event, dict)
                          else {"type": "raw", "data": line})
    return events


def _short(value, width: int = 180) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 1] + "…"


def _content_text(event: dict) -> str:
    """Text carried in an ACP `content` list (where denials are reported)."""
    parts = []
    for item in event.get("content") or []:
        inner = item.get("content") if isinstance(item, dict) else None
        if isinstance(inner, dict) and inner.get("text"):
            parts.append(str(inner["text"]))
    return " ".join(parts)


def denied_calls(events: list[dict]) -> list[str]:
    """Tool calls grok's permission policy refused, as 'input -> reason'."""
    inputs = {e.get("toolCallId"): e.get("rawInput") for e in events
              if e.get("type") == "tool_call"}
    out = []
    for event in events:
        text = _content_text(event)
        # status check: a completed read of a file that quotes a denial is not one
        if event.get("type") == "tool_call_update" and event.get("status") == "failed" \
                and "Denied by permission" in text:
            raw = inputs.get(event.get("toolCallId")) or {}
            what = raw.get("command") or raw.get("file_path") or raw.get("target_file") or raw
            out.append(f"{_short(what, 120)} -> {_short(text, 160)}")
    return out


def codex_denials(stderr_log: Path) -> list[str]:
    """Commands codex's execpolicy refused, as 'command -> reason': they show
    up on stderr only, inside an escaped error message."""
    try:
        text = Path(stderr_log).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if "exec_command failed" not in line or "rejected:" not in line:
            continue
        clean = line.replace("\\", "")
        match = re.search(r"-Command '(.*?)'` rejected: ([^\"]*)", clean)
        out.append(f"{_short(match.group(1), 120)} -> {match.group(2)}" if match
                   else _short(clean.split("error=", 1)[-1], 200))
    return out


CODEX_EVENTS = {"thread.started", "turn.started", "turn.completed", "turn.failed",
                "item.started", "item.updated", "item.completed"}


def _codex_line(event: dict) -> str | None:
    kind, item = event.get("type"), event.get("item") or {}
    itype = item.get("type")
    if kind == "thread.started":
        return f"thread.started: {event.get('thread_id')}"
    if kind == "turn.completed":
        usage = event.get("usage") or {}
        return (f"end: tokens in={usage.get('input_tokens')} "
                f"cached={usage.get('cached_input_tokens')} out={usage.get('output_tokens')} "
                f"reasoning={usage.get('reasoning_output_tokens')}")
    if kind == "turn.failed":
        return f"ERROR: {_short((event.get('error') or {}).get('message', event))}"
    if kind == "item.started":  # the rest is reported on completion
        return f"exec: {_short(item.get('command', ''))}" \
            if itype == "command_execution" else None
    if itype == "agent_message":
        return f"text: {_short(item.get('text', ''))}"
    if itype == "reasoning":
        return f"thought: {_short(item.get('text', ''))}"
    if itype == "command_execution":
        return f"exec [exit {item.get('exit_code')}]: " \
               f"{_short(item.get('aggregated_output', ''))}"
    if itype == "file_change":
        changes = ", ".join(f"{c.get('kind')} {c.get('path')}"
                            for c in item.get("changes") or [])
        return f"file_change [{item.get('status')}]: {_short(changes)}"
    rest = {k: v for k, v in item.items() if k not in ("id", "type")}
    return f"{itype or kind}: {_short(rest)}"


def describe_events(events: list[dict], last: int) -> list[str]:
    merged: list[dict] = []
    for event in events:
        kind = event.get("type", "?")
        if kind in ("available_commands", "usage", "turn.started", "item.updated") or (
                kind == "tool_call_update" and event.get("status") is None) or (
                kind == "item.started" and _codex_line(event) is None):
            continue  # bookkeeping noise
        if kind in ("text", "thought") and merged and merged[-1].get("type") == kind:
            merged[-1]["data"] += str(event.get("data", ""))
        elif kind in ("text", "thought"):
            merged.append({"type": kind, "data": str(event.get("data", ""))})
        else:
            merged.append(event)
    lines = []
    for event in merged[-last:] if last else merged:
        kind = event.get("type", "?")
        if kind in CODEX_EVENTS:
            lines.append(_codex_line(event))
        elif kind in ("text", "thought", "raw"):
            lines.append(f"{kind}: {_short(event.get('data', ''))}")
        elif kind == "tool_call":
            name = event.get("toolName") or event.get("title") or "?"
            lines.append(f"tool_call {name}: {_short(event.get('rawInput', ''))}")
        elif kind == "tool_call_update":
            body = event.get("rawOutput")
            if isinstance(body, dict) and "output_for_prompt" in body:
                body = body["output_for_prompt"]
            if body is None:
                body = _content_text(event)
            lines.append(f"tool_update [{event.get('status')}]: {_short(body)}")
        elif kind == "end":
            lines.append(f"end: stopReason={event.get('stopReason')} "
                         f"turns={event.get('num_turns')} "
                         f"cost_usd={event.get('total_cost_usd')}")
        elif kind == "error":
            lines.append(f"ERROR: {_short(event.get('message', event))}")
        else:
            rest = {k: v for k, v in event.items() if k != "type"}
            lines.append(f"{kind}: {_short(rest)}")
    return lines


# --------------------------------------------------------------------------
# spawn / resume / status / list
# --------------------------------------------------------------------------

def ensure_local_excludes() -> None:
    """Keep .orch/, .worktrees/ and the codex rules out of `git add -A`
    whatever the base commit's .gitignore says (info/exclude is shared by
    every worktree)."""
    exclude = Path(git("rev-parse", "--path-format=absolute",
                       "--git-common-dir").strip()) / "info" / "exclude"
    current = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    missing = [p for p in (".orch/", ".worktrees/", "/.codex/") if p not in current.split()]
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with open(exclude, "a", encoding="utf-8") as handle:
            handle.write(("" if current.endswith("\n") or not current else "\n")
                         + "\n".join(missing) + "\n")


def refs_snapshot() -> dict[str, str]:
    out = git("for-each-ref", "--format=%(refname) %(objectname)",
              "refs/heads", "refs/tags")
    return dict(line.split(" ", 1) for line in out.splitlines() if line)


def cmd_spawn(args) -> int:
    pkg = check_pkg(args.pkg)
    brief = ORCH / "briefs" / f"{pkg}.md"
    if not brief.is_file():
        raise OrchError(f"brief not found: {rel(brief)}")
    text = brief.read_text(encoding="utf-8-sig")
    first = next((ln.strip().lstrip("# ").strip() for ln in text.splitlines()
                  if ln.strip()), "")
    if not first.startswith(ROLE_LINE):
        raise OrchError(f"{rel(brief)} must start with '{ROLE_LINE}'")

    old = _read_json(state_path(pkg))
    if old and not old.get("cleaned_at"):
        raise OrchError(f"package {pkg} already exists; cleanup it first")
    worktree, branch = WORKTREES / pkg, BRANCH_PREFIX + pkg
    if worktree.exists():
        raise OrchError(f"{rel(worktree)} already exists")
    if git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{branch}"):
        raise OrchError(f"branch {branch} already exists")
    base_sha = git("rev-parse", "--verify", f"{args.base}^{{commit}}").strip()
    running = [p for p in all_packages() if is_running(p)]
    if len(running) >= args.max_parallel:
        raise OrchError(f"{len(running)} package(s) already running "
                        f"({', '.join(running)}); limit is {args.max_parallel}")
    cmd, version = executor_version(args.executor)

    ensure_local_excludes()
    snapshot = refs_snapshot()
    git("worktree", "add", "-b", branch, str(worktree), base_sha)
    (worktree / ".orch").mkdir(exist_ok=True)
    shutil.copyfile(brief, worktree / ".orch" / "brief.md")

    logs = ORCH / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for name in (f"{pkg}.jsonl", f"{pkg}.stderr.log", f"{pkg}.supervisor.log"):
        if (logs / name).exists():  # left by an earlier incarnation of this id
            (logs / name).rename(logs / f"{name}.{stamp}.old")
    for stale in (ORCH / "state").glob(f"{pkg}.run*.json"):
        stale.unlink()

    state = {
        "pkg": pkg, "branch": branch, "worktree": str(worktree),
        "base": args.base, "base_sha": base_sha, "created_at": now_iso(),
        "executor": args.executor, "executor_cmd": cmd, "executor_version": version,
        # codex picks its own thread id; session_id() reads it from the log
        "session_id": str(uuid.uuid4()) if args.executor == "grok" else None,
        "model": args.model, "trust": not args.no_trust,
        "python": sys.executable,
        "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest(),
        "allow_paths": allow_paths_from_brief(text),
        "log": str(logs / f"{pkg}.jsonl"),
        "stderr_log": str(logs / f"{pkg}.stderr.log"),
        "refs_at_spawn": snapshot, "runs": [],
        "llm_max_calls": args.llm_key,
    }
    print(f"package   {pkg}")
    print(f"executor  {args.executor} ({version})")
    print(f"worktree  {rel(worktree)} on {branch} from {args.base} ({base_sha[:12]})")
    print(f"session   {state['session_id'] or 'reported by codex once it starts'}")
    print(f"log       {rel(state['log'])}")
    if args.llm_key is not None:
        found = "found" if llm_key() else "NOT FOUND, the package runs without it"
        print(f"llm key   given to {args.executor} ({found}); {LLM_CAP_ENV}={args.llm_key}")
    if not state["allow_paths"]:
        print("note      brief has no ```allow-paths block; review will only "
              "check the protected paths")
    return start_run(state, "spawn", SPAWN_PROMPT, args.timeout, args.detach)


def cmd_resume(args) -> int:
    pkg = check_pkg(args.pkg)
    state = load_state(pkg)
    if state.get("cleaned_at"):
        raise OrchError(f"package {pkg} was cleaned up")
    feedback = Path(args.feedback)
    if not feedback.is_file():
        raise OrchError(f"feedback file not found: {feedback}")
    worktree = Path(state["worktree"])
    if not worktree.is_dir():
        raise OrchError(f"worktree missing: {rel(worktree)}")
    if run_status(state)["phase"] in ("running", "starting"):
        raise OrchError(f"package {pkg} is still running")
    rounds = sum(1 for run in state["runs"] if run["kind"] == "resume")
    if rounds >= args.max_rework and not args.force:
        raise OrchError(
            f"package {pkg} already had {rounds} rework round(s); the limit is "
            f"{args.max_rework}. Stop and ask the user (or pass --force).")
    if not state.get("session_id"):
        state["session_id"] = session_id(state)
        if not state["session_id"]:
            raise OrchError(f"{executor_of(state)} reported no session id for {pkg}; "
                            f"`handover {pkg}` starts a fresh session on the worktree")
    name = f"review-{rounds + 1}.md"
    shutil.copyfile(feedback, worktree / ".orch" / name)
    state.pop("review", None)  # the old review no longer covers the branch
    print(f"resume    {pkg}: rework round {rounds + 1}, feedback at "
          f"{rel(worktree / '.orch' / name)}")
    return start_run(state, "resume", RESUME_PROMPT.format(name=name),
                     args.timeout, args.detach)


def cmd_handover(args) -> int:
    """Start a fresh executor session (another executor, or the same one) on
    a package's worktree, keeping its commits and uncommitted changes. Not a
    rework round."""
    pkg = check_pkg(args.pkg)
    state = load_state(pkg)
    if state.get("cleaned_at") or state.get("merged"):
        raise OrchError(f"package {pkg} was already cleaned up or merged")
    if not Path(state["worktree"]).is_dir():
        raise OrchError(f"worktree missing: {rel(state['worktree'])}")
    if run_status(state)["phase"] in ("running", "starting"):
        raise OrchError(f"package {pkg} is still running")
    cmd, version = executor_version(args.executor)
    state.setdefault("handovers", []).append({
        "at": now_iso(), "from": executor_of(state), "to": args.executor,
        "from_session": session_id(state), "after_run": len(state["runs"])})
    state.update(executor=args.executor, executor_cmd=cmd, executor_version=version,
                 model=args.model,
                 session_id=str(uuid.uuid4()) if args.executor == "grok" else None)
    state.pop("review", None)
    print(f"handover  {pkg}: {state['handovers'][-1]['from']} -> {args.executor} "
          f"({version}); worktree and uncommitted changes kept")
    return start_run(state, "handover", HANDOVER_PROMPT, args.timeout, args.detach)


def branch_summary(state: dict) -> tuple[str, int]:
    head = git("rev-parse", "--verify", "--quiet", state["branch"], check=False).strip()
    if not head:
        return "", 0
    count = git("rev-list", "--count", f"{state['base_sha']}..{head}").strip()
    return head, int(count or 0)


def print_status(state: dict, info: dict, tail: int) -> None:
    pkg, record = state["pkg"], info["record"]
    print(f"package   {pkg}")
    if state.get("cleaned_at"):
        print(f"phase     cleaned up at {state['cleaned_at']}")
        return
    phase = info["phase"]
    if phase == "none":
        print("phase     no run yet")
    else:
        detail = f"run {info['n']}, {info['run']['kind']}"
        if phase == "finished":
            outcome = "TIMED OUT" if record.get("timed_out") else \
                f"exit {record.get('exit_code')}"
            if record.get("error"):
                outcome += f" ({record['error']})"
            print(f"phase     finished ({detail}): {outcome}")
        elif phase == "lost":
            print(f"phase     LOST ({detail}): no live process and no exit record")
        else:
            print(f"phase     {phase} ({detail})")
        print(f"elapsed   {fmt_duration(info['elapsed'])} of "
              f"{info['run']['timeout_min']:g}m timeout")
    print(f"executor  {executor_of(state)}")
    print(f"session   {session_id(state) or '(not reported yet)'}")
    head, ahead = branch_summary(state)
    print(f"branch    {state['branch']} @ {head[:12] or '?'} "
          f"({ahead} commit(s) on top of {state['base']} {state['base_sha'][:12]})")
    worktree = Path(state["worktree"])
    if worktree.is_dir():
        dirty = [ln for ln in git("status", "--porcelain", cwd=worktree).splitlines() if ln]
        report = "present" if (worktree / ".orch" / "report.md").is_file() else "missing"
        print(f"worktree  {rel(worktree)} ({len(dirty)} uncommitted path(s); report {report})")
    else:
        print(f"worktree  {rel(worktree)} (missing)")
    if state.get("merged"):
        print(f"merged    into {state['merged']['into']} as {state['merged']['commit'][:12]}")
    events = read_events(Path(state["log"]))
    print(f"log       {rel(state['log'])} ({len(events)} event(s))")
    for line in describe_events(events, tail):
        print(f"  {line}")


def cmd_status(args) -> int:
    pkg = check_pkg(args.pkg)
    state = load_state(pkg)
    while True:
        info = run_status(state)
        if info["phase"] not in ("running", "starting"):
            break
        limit = args.timeout if args.timeout is not None else info["run"]["timeout_min"]
        if info["elapsed"] > limit * 60:
            print(f"timeout   {fmt_duration(info['elapsed'])} > {limit:g}m, terminating")
            stop_run(state, info, "timeout")
            info = run_status(state)
            break
        if not args.wait:
            break
        time.sleep(args.interval)
    print_status(state, info, args.tail)
    if info["phase"] in ("running", "starting"):
        return 10
    record = info["record"]
    ok = info["phase"] == "finished" and record.get("exit_code") == 0 \
        and not record.get("timed_out")
    return 0 if ok else 2


def cmd_list(args) -> int:
    packages = all_packages()
    if not packages:
        print("no packages")
        return 0
    for pkg in packages:
        state = load_state(pkg)
        if state.get("cleaned_at"):
            phase = "cleaned"
        else:
            info = run_status(state)
            phase = info["phase"]
            if phase == "finished":
                record = info["record"]
                phase = "timed-out" if record.get("timed_out") else \
                    f"exit {record.get('exit_code')}"
            if state.get("merged"):
                phase += f", merged into {state['merged']['into']}"
        print(f"{pkg:<24} {state['branch']:<30} base {state['base']:<14} "
              f"{executor_of(state):<6} {phase}")
    return 0


# --------------------------------------------------------------------------
# review
# --------------------------------------------------------------------------

def changed_files(base: str, head: str) -> list[tuple[str, str, str | None]]:
    """(status, path, old_path) per changed file, renames detected."""
    parts = git("diff", "--name-status", "-M", "-z", base, head).split("\0")
    out, i = [], 0
    while i < len(parts) and parts[i]:
        status = parts[i]
        if status[0] in "RC":
            out.append((status, parts[i + 2], parts[i + 1]))
            i += 3
        else:
            out.append((status, parts[i + 1], None))
            i += 2
    return out


def parse_diff(text: str) -> dict[str, list[dict]]:
    """Per file, the hunks of a -U0 diff as removed/added (lineno, text) lists.
    Hunk bodies are consumed by the counts in the @@ header, so content that
    itself starts with '--- ' or '+++ ' (SQL comments) cannot be mistaken for
    a file header."""
    files: dict[str, list[dict]] = {}
    current, hunk, old_path = None, None, ""
    old_left = new_left = old_no = new_no = 0
    for line in text.splitlines():
        if old_left or new_left:
            if line.startswith("-") and old_left:
                hunk["removed"].append((old_no, line[1:]))
                old_no += 1
                old_left -= 1
            elif line.startswith("+") and new_left:
                hunk["added"].append((new_no, line[1:]))
                new_no += 1
                new_left -= 1
            continue
        if line.startswith("diff --git "):
            current = None
        elif line.startswith("--- "):
            old_path = line[4:].strip().removeprefix("a/")
        elif line.startswith("+++ "):
            path = line[4:].strip()
            path = old_path if path == "/dev/null" else path.removeprefix("b/")
            current = files.setdefault(path, [])
        else:
            match = HUNK_RE.match(line)
            if match and current is not None:
                old_no, new_no = int(match.group(1)), int(match.group(3))
                old_left = int(match.group(2) or 1)
                new_left = int(match.group(4) or 1)
                hunk = {"removed": [], "added": []}
                current.append(hunk)
    return files


def mask(token: str) -> str:
    return f"{token[:3]}…({len(token)} chars)"


def llm_key() -> str | None:
    """The DeepSeek key: this process's environment, else (Windows) the user's
    persistent environment, so the user can set it without restarting the
    orchestrator. Never printed or logged."""
    value = os.environ.get("DEEPSEEK_API_KEY", "")
    if value:
        return value
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                value, _ = winreg.QueryValueEx(handle, "DEEPSEEK_API_KEY")
        except OSError:
            return None
        return value or None
    return None


def scan_secrets(lines) -> list[tuple[str, str]]:
    """(where, description) for each suspicious line; values are never echoed."""
    hits = []
    key = llm_key()
    exact = key if key and len(key) >= 8 else None
    for where, text in lines:
        if exact and exact in text:
            hits.append((where, "the DeepSeek key itself"))
            continue
        for label, pattern in SECRET_RES:
            match = pattern.search(text)
            if match:
                hits.append((where, f"{label}: {mask(match.group(0))}"))
                break
    return hits


def parse_pytest_counts(output: str) -> dict[str, int]:
    for line in reversed(output.splitlines()):
        found = PYTEST_COUNT_RE.findall(line)
        if found and " in " in line:
            return {("error" if name.startswith("error") else name): int(count)
                    for count, name in found}
    return {}


def run_captured(cmd: list[str], cwd: Path, env: dict, timeout_s: float) -> dict:
    started = time.time()
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                **_own_group())
    except OSError as exc:
        return {"cmd": cmd, "rc": None, "output": str(exc), "seconds": 0.0,
                "timed_out": False}
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(proc.pid)
        out, _ = proc.communicate()
    return {"cmd": cmd, "rc": proc.returncode, "output": _decode(out or b""),
            "seconds": time.time() - started, "timed_out": timed_out}


def _tail(text: str, count: int) -> str:
    return "\n".join(text.rstrip().splitlines()[-count:])


def _fence(text: str, lang: str = "text") -> list[str]:
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return [f"{ticks}{lang}", text.rstrip("\n"), ticks]


def _listing(items: list[str], limit: int = 40) -> list[str]:
    lines = [f"- {item}" for item in items[:limit]]
    if len(items) > limit:
        lines.append(f"- …… 另有 {len(items) - limit} 处")
    return lines or ["- 无"]


def cmd_review(args) -> int:
    pkg = check_pkg(args.pkg)
    state = load_state(pkg)
    worktree = Path(state["worktree"])
    if state.get("cleaned_at") or not worktree.is_dir():
        raise OrchError(f"package {pkg} has no worktree to review")
    info = run_status(state)
    if info["phase"] in ("running", "starting"):
        raise OrchError(f"package {pkg} is still running; use `status {pkg} --wait`")
    branch, base = state["branch"], state["base_sha"]
    head = git("rev-parse", branch).strip()
    record = info["record"]
    flags: list[str] = []
    doc: list[str] = [f"# 审查包 · {pkg}", ""]

    # ---- header ----
    outcome = "未运行"
    if info["phase"] == "finished":
        outcome = "超时被终止" if record.get("timed_out") else \
            f"退出码 {record.get('exit_code')}"
        if record.get("timed_out") or record.get("exit_code") != 0:
            flags.append(f"执行者最近一轮非正常结束（{outcome}）")
    elif info["phase"] == "lost":
        outcome = "进程丢失，没有退出记录"
        flags.append("执行者最近一轮没有退出记录（进程丢失）")
    rework = sum(1 for run in state["runs"] if run["kind"] == "resume")
    commits = [ln for ln in git("log", "--reverse", "--format=%h %an: %s",
                                f"{base}..{head}").splitlines() if ln]
    executor = executor_of(state)
    handovers = "；换过执行者：" + "，".join(
        f"第 {h['after_run']} 轮之后 {h['from']} → {h['to']}"
        for h in state["handovers"]) if state.get("handovers") else ""
    doc += [
        f"- 生成时间：{now_iso()}",
        f"- 基线：`{state['base']}`（{base[:12]}）",
        f"- 分支：`{branch}` @ {head[:12]}，基线之上 {len(commits)} 个提交",
        f"- 运行：共 {len(state['runs'])} 轮（返工 {rework} 轮），最近一轮{outcome}，"
        f"用时 {fmt_duration(info['elapsed'])}",
        f"- 执行者：{executor} "
        f"{state.get('executor_version') or state.get('grok_version') or '?'}；"
        f"会话 `{session_id(state)}`{handovers}",
        "",
    ]
    if executor == "codex":
        rules = worktree / CODEX_RULES
        if not rules.is_file() or rules.read_text(encoding="utf-8", errors="replace") \
                != codex_rules_text():
            flags.append(f"codex 的 execpolicy 规则 `{CODEX_RULES}` 被改过或删了")
        if state.get("rules_changed"):
            flags.append(f"派发后有 {len(state['rules_changed'])} 轮开始前发现规则文件被改过"
                         "（已重写）")
    if not commits:
        flags.append("分支上没有新提交")
    checked_out = git("rev-parse", "--abbrev-ref", "HEAD", cwd=worktree).strip()
    if checked_out != branch:
        flags.append(f"worktree 当前检出的是 `{checked_out}` 而不是 `{branch}`，"
                     "下面的复跑结果不对应被审分支")
    dirty = [ln for ln in git("status", "--porcelain", cwd=worktree).splitlines() if ln]
    if dirty:
        flags.append(f"worktree 有 {len(dirty)} 处未提交改动（复跑会包含它们，合并不会）")
    brief_src = ORCH / "briefs" / f"{pkg}.md"
    brief_copy = worktree / ".orch" / "brief.md"
    for label, path in (("编排者的 brief", brief_src), ("worktree 里的 brief 副本", brief_copy)):
        if not path.is_file():
            flags.append(f"{label}不见了：{rel(path)}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != state["brief_sha256"]:
            flags.append(f"{label}在派发后被改过：{rel(path)}")

    # ---- 1. changed files ----
    protected = list(PROTECTED)
    for tag, paths in FROZEN_AFTER.items():
        if git_ok("show-ref", "--verify", "--quiet", f"refs/tags/{tag}"):
            protected += paths
    allow = state.get("allow_paths") or []
    files = changed_files(base, head)
    rows, forbidden, outside, config_changes, secret_files, deleted_tests = \
        [], [], [], [], [], []
    for status, path, old in files:
        marks = []
        touched = [path] + ([old] if old else [])
        if any(matches_any(p, protected) for p in touched):
            marks.append("**越界：禁区**")
            forbidden.append(path)
        elif allow and not all(matches_any(p, allow) for p in touched):
            marks.append("**越界：不在允许路径内**")
            outside.append(path)
        if Path(path).name in TEST_CONFIG_NAMES:
            marks.append("测试配置")
            config_changes.append(f"`{path}`（{status}）")
        if status[0] != "D" and SECRET_FILE_RE.search(path):
            marks.append("**敏感文件名**")
            secret_files.append(path)
        if status[0] == "D" and TEST_PATH_RE.search(path):
            deleted_tests.append(path)
        shown = f"`{old}` → `{path}`" if old else f"`{path}`"
        rows.append(f"| {status} | {shown} | {'；'.join(marks)} |")
    if forbidden:
        flags.append(f"改动了禁区路径 {len(forbidden)} 处：{', '.join(forbidden[:5])}")
    if outside:
        flags.append(f"改动超出 brief 允许的路径 {len(outside)} 处：{', '.join(outside[:5])}")
    if deleted_tests:
        flags.append(f"删除了测试文件 {len(deleted_tests)} 个：{', '.join(deleted_tests[:5])}")
    doc += ["## 1. 改动文件（相对基线，已识别重命名）", ""]
    doc.append("允许路径（取自派发时的 brief）："
               + ("、".join(f"`{p}`" for p in allow) if allow
                  else "brief 没有 allow-paths 块，只按禁区检查"))
    doc.append("禁区：" + "、".join(f"`{p}`" for p in protected))
    doc.append("")
    if rows:
        doc += ["| 状态 | 路径 | 标记 |", "|---|---|---|", *rows]
    else:
        doc.append("没有改动。")
    if dirty:
        doc += ["", "未提交的改动（`git status --porcelain`）：", "",
                *_fence("\n".join(dirty[:60]))]
    doc += ["", "提交：", "", *_listing(commits), ""]

    # ---- 2. diff stat ----
    doc += ["## 2. diff 统计", "",
            *_fence(git("diff", "--stat", "-M", base, head).rstrip() or "（空）"), ""]
    renames = [f for f in files if f[0].startswith("R")]
    if renames:
        pure = sum(1 for f in renames if f[0] == "R100")
        doc += [f"重命名 {len(renames)} 个，其中内容完全不变（R100）{pure} 个。", ""]

    # ---- 3. re-run ----
    doc += ["## 3. 独立复跑（在 worktree 里，环境里去掉了 "
            + "、".join(STRIP_ENV) + "）", ""]
    env, _ = child_env(worktree)
    framework = worktree / "framework"
    counts: dict[str, int] = {}
    if args.skip_tests:
        doc += ["按 `--skip-tests` 跳过了 pytest 与门槛。", ""]
        flags.append("本次审查包没有复跑测试（--skip-tests）")
    elif not framework.is_dir():
        doc += ["worktree 里没有 `framework/`，无法复跑。", ""]
        flags.append("worktree 里没有 framework/ 目录")
    else:
        test = run_captured([args.python, "-m", "pytest", "-q", "testing", "tests"],
                            framework, env, args.test_timeout * 60)
        counts = parse_pytest_counts(test["output"])
        summary = "，".join(f"{k} {v}" for k, v in counts.items()) or "没有解析出统计行"
        doc += [f"`cd framework && {Path(args.python).name} -m pytest -q testing tests`"
                f" → 退出码 {test['rc']}，{fmt_duration(test['seconds'])}；{summary}", "",
                *_fence(_tail(test["output"], 25)), ""]
        if test["timed_out"]:
            flags.append(f"pytest 超过 {args.test_timeout:g} 分钟被终止")
        elif test["rc"] != 0:
            flags.append(f"pytest 未通过（退出码 {test['rc']}；{summary}）")
        if args.expect_passed is not None and counts.get("passed", 0) < args.expect_passed:
            flags.append(f"通过数 {counts.get('passed', 0)} 少于预期的 {args.expect_passed}")
        if (framework / "surprise" / "gates" / "all.py").is_file():
            gates = run_captured([args.python, "-m", "surprise.gates.all"],
                                 framework, env, args.test_timeout * 60)
            doc += [f"`cd framework && {Path(args.python).name} -m surprise.gates.all`"
                    f" → 退出码 {gates['rc']}，{fmt_duration(gates['seconds'])}", "",
                    *_fence(_tail(gates["output"], 25)), ""]
            if gates["timed_out"] or gates["rc"] != 0:
                flags.append(f"门槛未通过（退出码 {gates['rc']}）")
        else:
            doc += ["门槛：`framework/surprise/gates/all.py` 还不存在，跳过"
                    "（S1 建立之后才有）。", ""]
        after = [ln for ln in git("status", "--porcelain", cwd=worktree).splitlines() if ln]
        new_dirt = sorted(set(after) - set(dirty))
        if new_dirt:
            doc += ["复跑之后 worktree 多出的未提交改动（测试在写受跟踪的路径？）：", "",
                    *_fence("\n".join(new_dirt[:40])), ""]

    # ---- 4. scans ----
    hunks = parse_diff(git("diff", "-U0", "-M", "--no-color", "--no-ext-diff", base, head))
    skips, excepts, removed_asserts, changed_asserts, other_asserts = [], [], [], [], 0
    added_lines = []
    for path, file_hunks in hunks.items():
        is_test = bool(TEST_PATH_RE.search(path))
        for hunk in file_hunks:
            for lineno, text in hunk["added"]:
                added_lines.append((f"{path}:{lineno}", text))
                if SKIP_RE.search(text):
                    skips.append(f"`{path}:{lineno}` `{_short(text.strip(), 140)}`")
                if path.endswith(".py") and BROAD_EXCEPT_RE.search(text):
                    excepts.append(f"`{path}:{lineno}` `{_short(text.strip(), 140)}`")
            gone = [(n, t) for n, t in hunk["removed"] if ASSERT_RE.search(t)]
            if not gone:
                continue
            if not is_test:
                other_asserts += len(gone)
                continue
            new = [t for _, t in hunk["added"] if ASSERT_RE.search(t)]
            for lineno, text in gone:
                entry = f"`{path}:{lineno}` 原：`{_short(text.strip(), 140)}`"
                if new:
                    entry += " → 同一处新增：" + "；".join(
                        f"`{_short(t.strip(), 140)}`" for t in new[:3])
                    changed_asserts.append(entry)
                else:
                    removed_asserts.append(entry)
    if skips:
        flags.append(f"新增 skip / xfail / 排除测试 {len(skips)} 处")
    if removed_asserts:
        flags.append(f"测试里被删的断言 {len(removed_asserts)} 处")
    if changed_asserts:
        flags.append(f"测试里被改写的断言 {len(changed_asserts)} 处（逐条确认没有放宽）")
    if excepts:
        flags.append(f"新增宽泛的异常捕获 {len(excepts)} 处（确认没有吞掉失败）")
    if config_changes:
        flags.append(f"测试配置文件有改动：{'、'.join(config_changes)}")
    report_path = worktree / ".orch" / "report.md"
    report = report_path.read_text(encoding="utf-8", errors="replace") \
        if report_path.is_file() else None
    secrets = scan_secrets(added_lines)
    if report:
        secrets += scan_secrets((f".orch/report.md:{i}", line)
                                for i, line in enumerate(report.splitlines(), 1))
    events = read_events(Path(state["log"]))
    stderr_text = Path(state["stderr_log"]).read_text(encoding="utf-8", errors="replace") \
        if Path(state["stderr_log"]).is_file() else ""
    log_hits = len(scan_secrets(("log", json.dumps(e, ensure_ascii=False))
                                for e in events))
    log_hits += len(scan_secrets(("stderr", line) for line in stderr_text.splitlines()))
    if secrets or secret_files:
        flags.append(f"疑似密钥 {len(secrets)} 处、敏感文件名 {len(secret_files)} 个")
    if log_hits:
        flags.append(f"执行者日志里有 {log_hits} 行疑似密钥（日志不入库，但要查来源）")
    doc += ["## 4. 扫描（只看相对基线新增或删除的行）", "",
            "### 4.1 新增的 skip / xfail / 排除测试", "", *_listing(skips), "",
            "### 4.2 测试里被删的断言", "", *_listing(removed_asserts), "",
            "### 4.3 测试里被改写的断言（可能放宽）", "", *_listing(changed_asserts), ""]
    if other_asserts:
        doc += [f"非测试文件里另有 {other_asserts} 行被删的 assert，读 diff 时留意。", ""]
    doc += ["### 4.4 新增的宽泛异常捕获", "", *_listing(excepts), "",
            "### 4.5 测试配置改动（conftest 等）", "", *_listing(config_changes), "",
            "### 4.6 疑似密钥（值已打码）", "",
            *_listing([f"`{where}` {what}" for where, what in secrets]
                      + [f"`{p}` 敏感文件名" for p in secret_files]),
            f"- 日志 `{rel(state['log'])}` 与 stderr 中疑似密钥行数：{log_hits}", ""]

    # ---- 5. refs ----
    before, now = state.get("refs_at_spawn", {}), refs_snapshot()
    own = f"refs/heads/{branch}"
    ref_changes, tag_changes = [], 0
    for ref in sorted(set(before) | set(now)):
        if ref == own or before.get(ref) == now.get(ref):
            continue
        if ref not in before:
            ref_changes.append(f"新增 `{ref}` @ {now[ref][:12]}")
        elif ref not in now:
            ref_changes.append(f"删除 `{ref}`（原 {before[ref][:12]}）")
        else:
            ref_changes.append(f"移动 `{ref}` {before[ref][:12]} → {now[ref][:12]}")
        if ref.startswith("refs/tags/") or ref not in now:
            tag_changes += 1
    if tag_changes:
        flags.append(f"派发以来有 {tag_changes} 处 tag 变化或 ref 被删："
                     "确认是编排者自己做的，不是执行者")
    main_dirty = [ln for ln in git("status", "--porcelain").splitlines() if ln]
    doc += ["## 5. worktree 之外的变化", "",
            "执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。",
            "", "派发以来其他 ref 的变化：", "", *_listing(ref_changes), "",
            "主检出区当前未提交的改动（`git status --porcelain`）：", "",
            *_fence("\n".join(main_dirty[:60]) or "（干净）"), ""]

    # ---- 6. log ----
    kinds: dict[str, int] = {}
    for event in events:
        kinds[event.get("type", "?")] = kinds.get(event.get("type", "?"), 0) + 1
    errors = [e for e in events if e.get("type") in ("error", "turn.failed")]
    if errors:
        flags.append(f"执行者日志里有 {len(errors)} 条 error / turn.failed 事件")
    ends = [e for e in events if e.get("type") == "end"]
    cost = sum(e.get("total_cost_usd") or 0 for e in ends)
    turns = sum(e.get("num_turns") or 0 for e in ends)
    usage: dict[str, int] = {}
    for event in events:
        if event.get("type") == "turn.completed":
            for key, value in (event.get("usage") or {}).items():
                usage[key] = usage.get(key, 0) + (value or 0)
    spend = []
    if ends or not usage:
        spend.append(f"grok：{turns} 个模型回合，上报花费 {cost:.4f} 美元（没上报的轮次按 0 计）")
    if usage:
        spend.append(f"codex：{sum(1 for e in events if e.get('type') == 'turn.completed')}"
                     f" 轮，输入 {usage.get('input_tokens', 0)} token（其中缓存 "
                     f"{usage.get('cached_input_tokens', 0)}），输出 "
                     f"{usage.get('output_tokens', 0)}（其中推理 "
                     f"{usage.get('reasoning_output_tokens', 0)}），codex 不报美元")
    spend = "；".join(spend)
    denied = denied_calls(events) + codex_denials(Path(state["stderr_log"]))
    doc += ["## 6. 执行日志摘要", "",
            f"`{rel(state['log'])}`：{len(events)} 条事件（"
            + "，".join(f"{k} {v}" for k, v in sorted(kinds.items())) + "）；"
            f"各轮合计 {spend}。", "",
            f"被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 "
            f"{len(denied)} 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：", "",
            *_listing([f"`{item}`" for item in denied]), "",
            "最后几条：", "", *_fence("\n".join(describe_events(events, 12)) or "（空）"),
            ""]

    # ---- 7. report ----
    doc += ["## 7. 执行者报告（`.orch/report.md`，自述，未经核实）", ""]
    if report is None:
        flags.append("执行者没有写 .orch/report.md")
        doc += ["缺失。", ""]
    else:
        doc += [*_fence(report, "markdown"), ""]

    # ---- flags + next steps, inserted after the header ----
    summary = ["## 红旗汇总", ""]
    summary += [f"- {flag}" for flag in flags] or ["- 自动检查没有发现红旗。"]
    summary += ["", "自动检查只是筛子，结论要等读完完整 diff 再下：", "",
                *_fence(f"git diff {state['base']}..{branch}\n"
                        f"git diff -M --stat {state['base']}..{branch}", "bash"), ""]
    doc[8:8] = summary
    doc += ["## 8. 结论（编排者填）", "",
            "合并 / 返工 / 推翻 / 升级，理由：", ""]

    out = ORCH / "reviews" / f"{pkg}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(doc), encoding="utf-8")
    state["review"] = {"at": now_iso(), "head": head, "flags": len(flags),
                       "tests": counts, "path": str(out)}
    save_state(state)
    print(f"review    {rel(out)}")
    print(f"head      {branch} @ {head[:12]} ({len(commits)} commit(s), "
          f"{len(files)} file(s) changed)")
    if counts:
        print("tests     " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"flags     {len(flags)}")
    for flag in flags:
        print(f"  - {flag}")
    if args.print:
        print()
        print("\n".join(doc))
    return 3 if flags else 0


# --------------------------------------------------------------------------
# merge / cleanup
# --------------------------------------------------------------------------

def _commit_message(subject: str, body: str = "") -> str:
    parts = [subject] + ([body] if body else [])
    trailer = os.environ.get("ORCH_COMMIT_TRAILER", "").strip()
    if trailer:
        parts.append(trailer)
    return "\n\n".join(parts)


def cmd_merge(args) -> int:
    pkg = check_pkg(args.pkg)
    state = load_state(pkg)
    if state.get("cleaned_at"):
        raise OrchError(f"package {pkg} was cleaned up")
    if state.get("merged"):
        raise OrchError(f"package {pkg} is already merged into {state['merged']['into']}")
    if run_status(state)["phase"] in ("running", "starting"):
        raise OrchError(f"package {pkg} is still running")
    session = args.session or session_of(pkg)
    if not session:
        raise OrchError(f"cannot tell the session from {pkg!r}; pass --session sNN")
    branch, worktree = state["branch"], Path(state["worktree"])
    head = git("rev-parse", branch).strip()
    review = state.get("review") or {}
    if review.get("head") != head and not args.force:
        raise OrchError(f"{branch} @ {head[:12]} has no review of that commit; "
                        f"run `review {pkg}` first (or pass --force)")
    if worktree.is_dir() and git("status", "--porcelain", cwd=worktree).strip() \
            and not args.force:
        raise OrchError(f"{rel(worktree)} has uncommitted changes that a merge "
                        "would leave behind (inspect them, or pass --force)")
    current = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if current != args.into:
        raise OrchError(f"main checkout is on {current!r}; `git switch {args.into}` first")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise OrchError("main checkout has uncommitted changes; commit them first")
    if git_ok("merge-base", "--is-ancestor", head, "HEAD"):
        raise OrchError(f"{branch} has nothing that {args.into} lacks")

    message = _commit_message(
        f"Merge {branch} into {args.into}",
        f"Work package {pkg}; base {state['base']} ({state['base_sha'][:12]}).")
    proc = subprocess.run(["git", "merge", "--no-ff", "-m", message, branch],
                          cwd=str(ROOT), capture_output=True)
    if proc.returncode != 0:
        detail = (_decode(proc.stdout) + _decode(proc.stderr)).strip()
        subprocess.run(["git", "merge", "--abort"], cwd=str(ROOT), capture_output=True)
        raise OrchError(f"merge failed and was aborted:\n{detail}")
    merge_sha = git("rev-parse", "HEAD").strip()

    dest = ARCHIVE / session
    dest.mkdir(parents=True, exist_ok=True)
    sources = [(ORCH / "briefs" / f"{pkg}.md", f"{pkg}.brief.md"),
               (worktree / ".orch" / "report.md", f"{pkg}.report.md"),
               (ORCH / "reviews" / f"{pkg}.md", f"{pkg}.review.md")]
    sources += [(path, f"{pkg}.rework{path.stem.split('-')[-1]}.md")
                for path in sorted((worktree / ".orch").glob("review-*.md"))]
    archived = []
    for source, name in sources:
        if source.is_file():
            shutil.copyfile(source, dest / name)
            archived.append(rel(dest / name))
        else:
            print(f"WARNING   nothing to archive at {rel(source)}")
    if archived:
        git("add", "--", *archived)
        git("commit", "-m", _commit_message(
            f"orch({session}): archive brief, report and review for {pkg}"))
    state["merged"] = {"into": args.into, "commit": merge_sha, "at": now_iso(),
                       "archived": archived}
    save_state(state)
    print(f"merged    {branch} into {args.into} as {merge_sha[:12]}")
    for path in archived:
        print(f"archived  {path}")
    return 0


def _rmtree(path: Path) -> None:
    def retry(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def cmd_cleanup(args) -> int:
    pkg = check_pkg(args.pkg)
    state = load_state(pkg)
    if state.get("cleaned_at"):
        print(f"package {pkg} was already cleaned up")
        return 0
    branch, worktree = state["branch"], Path(state["worktree"])
    info = run_status(state)
    if info["phase"] in ("running", "starting"):
        if not args.abandon:
            raise OrchError(f"package {pkg} is still running (--abandon stops it)")
        stop_run(state, info, "abandon")
    head = git("rev-parse", "--verify", "--quiet", branch, check=False).strip()
    target = (state.get("merged") or {}).get("into")
    merged = bool(head and target and git_ok("merge-base", "--is-ancestor", head, target))
    if not merged and not args.abandon:
        raise OrchError(f"{branch} is not merged; pass --abandon to throw it away")
    if merged and not args.abandon and worktree.is_dir() \
            and git("status", "--porcelain", cwd=worktree).strip():
        raise OrchError(f"{rel(worktree)} has uncommitted changes (--abandon discards them)")

    if worktree.exists():
        if not git_ok("worktree", "remove", "--force", str(worktree)) and worktree.exists():
            _rmtree(worktree)
    git("worktree", "prune")
    if head:
        git("branch", "-D", branch)
    state["cleaned_at"] = now_iso()
    state["abandoned"] = not merged
    save_state(state)
    print(f"cleaned   {pkg}: removed {rel(worktree)} and {branch} "
          f"({'merged' if merged else 'ABANDONED, unmerged'}); "
          f"logs stay in {rel(ORCH / 'logs')}")
    return 0


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok_worker.py",
        description="Dispatch work packages to headless grok or codex executors.")
    sub = parser.add_subparsers(dest="command", required=True)

    def run_options(p):
        p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_MIN,
                       help="minutes before the executor is terminated (default %(default)s)")
        p.add_argument("--detach", action="store_true",
                       help="return at once and leave a hidden supervisor process "
                            "behind (default: block until the executor exits)")

    def executor_options(p):
        p.add_argument("--executor", choices=EXECUTORS, default=DEFAULT_EXECUTOR,
                       help="who does the package (default %(default)s; ORCH_EXECUTOR)")
        p.add_argument("--model", help=f"model id (default: {CODEX_MODEL} for codex, "
                                       "grok's own default for grok)")

    p = sub.add_parser("spawn", help="create the worktree and start the executor on a brief")
    p.add_argument("pkg")
    p.add_argument("--base", required=True, help="tag, branch or commit to start from")
    executor_options(p)
    p.add_argument("--max-parallel", type=int, default=DEFAULT_MAX_PARALLEL,
                   help="refuse when this many packages are running (default %(default)s)")
    p.add_argument("--no-trust", action="store_true",
                   help="grok only: do not pass --trust (grok then skips CLAUDE.md)")
    p.add_argument("--llm-key", type=int, metavar="N",
                   help="give this package's executor DEEPSEEK_API_KEY and "
                        f"{LLM_CAP_ENV}=N (all its runs; review re-runs never get it)")
    run_options(p)
    p.set_defaults(func=cmd_spawn)

    p = sub.add_parser("status", help="running?, elapsed time, last log events")
    p.add_argument("pkg")
    p.add_argument("--timeout", type=float,
                   help="minutes; terminate when exceeded (default: the run's own)")
    p.add_argument("--tail", type=int, default=8, help="log events to show")
    p.add_argument("--wait", action="store_true", help="block until the executor has exited")
    p.add_argument("--interval", type=float, default=15, help="poll seconds for --wait")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("review", help="build the review package")
    p.add_argument("pkg")
    p.add_argument("--skip-tests", action="store_true", help="do not re-run pytest/gates")
    p.add_argument("--expect-passed", type=int,
                   help="flag the package when fewer tests pass than this")
    p.add_argument("--python", default=sys.executable,
                   help="interpreter for the re-run (default: the one running this tool)")
    p.add_argument("--test-timeout", type=float, default=DEFAULT_TEST_TIMEOUT_MIN,
                   help="minutes per re-run command (default %(default)s)")
    p.add_argument("--print", action="store_true", help="also print the whole package")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("resume", help="send review feedback into the same executor session")
    p.add_argument("pkg")
    p.add_argument("feedback", help="markdown file with the review comments")
    p.add_argument("--max-rework", type=int, default=DEFAULT_MAX_REWORK,
                   help="rework rounds allowed per package (default %(default)s)")
    p.add_argument("--force", action="store_true", help="exceed --max-rework")
    run_options(p)
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("handover", help="start a fresh session (any executor) on the "
                                        "package's worktree, keeping its changes")
    p.add_argument("pkg")
    executor_options(p)
    run_options(p)
    p.set_defaults(func=cmd_handover)

    p = sub.add_parser("merge", help="merge --no-ff and archive brief/report/review")
    p.add_argument("pkg")
    p.add_argument("--into", required=True, help="branch checked out in the main checkout")
    p.add_argument("--session", help="archive folder name (default: sNN from the package id)")
    p.add_argument("--force", action="store_true",
                   help="merge without a current review / with a dirty worktree")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("cleanup", help="remove the worktree and the branch")
    p.add_argument("pkg")
    p.add_argument("--abandon", action="store_true",
                   help="required when the branch is unmerged; also stops a running grok")
    p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("list", help="all packages and their state")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("_supervise")  # internal: the detached run supervisor
    p.add_argument("pkg")
    p.add_argument("run", type=int)
    p.set_defaults(func=lambda a: supervise(a.pkg, a.run))
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except OrchError as exc:
        print(f"grok_worker: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
