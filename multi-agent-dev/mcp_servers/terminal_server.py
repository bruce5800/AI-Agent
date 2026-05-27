"""Terminal MCP tools — execute shell commands within workspace."""

import os
import re
import shlex
import subprocess

from core.config import (
    COMMAND_ALLOWLIST,
    COMMAND_HARD_DENY_PATTERNS,
    COMMAND_TIMEOUT,
)

# Shell segment separators: && || ; |  (NOT && / || matched by | alone)
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|(?<!\|)\|(?!\|)")
_DENY_REGEXES = [re.compile(p) for p in COMMAND_HARD_DENY_PATTERNS]


def _executable_of(segment: str) -> str | None:
    """Extract the first real executable token from a shell segment.

    Skips leading env-var assignments like `FOO=bar python ...`.
    Returns None if segment is empty / unparseable.
    """
    seg = segment.strip()
    if not seg:
        return None
    try:
        tokens = shlex.split(seg, posix=True)
    except ValueError:
        return None
    for tok in tokens:
        if "=" in tok and tok.split("=", 1)[0].isidentifier():
            continue  # env-var prefix, skip
        # Strip a leading path so /usr/bin/python -> python
        return tok.rsplit("/", 1)[-1]
    return None


def _check_command_safety(command: str) -> str | None:
    """Return error string if command is denied, else None."""
    for rx in _DENY_REGEXES:
        if rx.search(command):
            return f"Error: command blocked by safety policy (matched: {rx.pattern})"

    segments = _SEGMENT_SPLIT.split(command)
    for seg in segments:
        exe = _executable_of(seg)
        if exe is None:
            continue  # empty segment — harmless
        if exe not in COMMAND_ALLOWLIST:
            return (
                f"Error: executable '{exe}' not in allowlist. "
                f"Allowed: {sorted(COMMAND_ALLOWLIST)}"
            )
    return None


def _venv_env(workspace: str) -> dict:
    """Build an env dict that prefers the workspace's `.venv` interpreter.

    If ``<workspace>/.venv/bin`` (or ``Scripts`` on Windows) exists, prepend
    it to PATH and set VIRTUAL_ENV. Any bare ``python``, ``pip``, ``pytest``
    invocation by an agent then resolves to the per-workspace venv instead
    of the Streamlit host's interpreter — no need for agents to know about
    it.

    Falls through gracefully to the host PATH if `.venv` doesn't exist
    (e.g. venv creation failed during workspace bootstrap).
    """
    env = os.environ.copy()
    venv_dir = os.path.join(workspace, ".venv")
    for bin_name in ("bin", "Scripts"):
        venv_bin = os.path.join(venv_dir, bin_name)
        if os.path.isdir(venv_bin):
            env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = venv_dir
            # Clear PYTHONHOME if set — would override venv site-packages
            env.pop("PYTHONHOME", None)
            break
    return env


def run_command(workspace: str, command: str, timeout: int = COMMAND_TIMEOUT) -> str:
    """Run a shell command in the workspace directory.

    Returns stdout + stderr. Timeout defaults to 30 seconds, hard cap 120s.
    Execution is cwd-bound to the workspace and uses the per-workspace
    ``.venv`` Python if one exists, so ``pip install`` / ``pytest`` /
    ``python ...`` don't pollute the Streamlit host's Python.
    """
    safety_error = _check_command_safety(command)
    if safety_error:
        return safety_error

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            env=_venv_env(workspace),
            capture_output=True,
            text=True,
            timeout=min(timeout, 120),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr

        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"

        return output.strip() if output.strip() else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {str(e)}"


TOOLS = {
    "run_command": {
        "function": run_command,
        "description": "Run a shell command in the workspace directory. Returns stdout + stderr. Only allowlisted executables (python, pip, pytest, node, npm, git, ls, cat, ...) may run.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30, max 120)"},
            },
            "required": ["command"],
        },
    },
}
