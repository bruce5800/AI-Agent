"""Workspace management — creation, isolation, cleanup."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from core.config import WORKSPACE_ROOT


def _create_venv(workspace_path: Path) -> tuple[bool, str]:
    """Create a per-workspace Python virtualenv at ``<ws>/.venv``.

    Returns (success, message). Failures are non-fatal: workspace creation
    still succeeds, and terminal_server.run_command falls back to the global
    interpreter (just like before this feature existed).

    Why per-workspace venv: the Reviewer agent issues ``pip install -r
    requirements.txt`` and similar against whatever Python is on PATH. Without
    isolation that's the Streamlit host Python — every demo run leaves new
    deps polluting your dev environment until something breaks.
    """
    venv_dir = workspace_path / ".venv"
    if venv_dir.exists():
        return True, "(already exists)"
    try:
        # `--symlinks` for speed/space; `ensurepip` default gives us pip
        result = subprocess.run(
            [sys.executable, "-m", "venv", "--symlinks", str(venv_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout).strip()[:200]
        return True, str(venv_dir)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def sanitize_name(name: str) -> str:
    """Convert a project name to a safe directory name."""
    # Keep alphanumeric, Chinese chars, hyphens, underscores
    name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:50] or "project"


def derive_project_slug(requirement: str, max_chars: int = 30) -> str:
    """Build a meaningful workspace slug from a free-form requirement string.

    Strategy: take the first `max_chars` of the requirement, sanitize, prepend
    a short timestamp so repeated runs don't all collide on the same slug.
    Falls back to "project" if requirement is empty.
    """
    import time
    head = (requirement or "").strip()[:max_chars]
    base = sanitize_name(head) or "project"
    stamp = time.strftime("%m%d_%H%M%S")
    return f"{base}_{stamp}"


def create_workspace(project_name: str) -> str:
    """Create a new workspace directory + per-workspace venv. Returns abs path.

    Venv creation is best-effort: failure logs to stderr and falls through so
    workspace creation always succeeds. terminal_server's PATH injection
    gracefully handles a missing ``.venv/bin``.
    """
    safe_name = sanitize_name(project_name)
    workspace_path = WORKSPACE_ROOT / safe_name

    # Avoid collision
    if workspace_path.exists():
        i = 1
        while (WORKSPACE_ROOT / f"{safe_name}_{i}").exists():
            i += 1
        workspace_path = WORKSPACE_ROOT / f"{safe_name}_{i}"

    workspace_path.mkdir(parents=True, exist_ok=True)

    ok, info = _create_venv(workspace_path)
    if not ok:
        print(f"[workspace] venv creation failed for {workspace_path}: {info}",
              file=sys.stderr)

    return str(workspace_path)


def _is_hidden_part(parts: tuple) -> bool:
    """True if any path component starts with '.' (i.e. .venv, .git, etc.)."""
    return any(p.startswith(".") for p in parts)


def list_workspaces() -> list[dict]:
    """List all existing workspaces.

    File counts exclude dot-dirs like ``.venv`` and ``.git`` — otherwise a
    fresh workspace shows ~2000 'files' just from venv site-packages.
    """
    if not WORKSPACE_ROOT.exists():
        return []
    results = []
    for d in sorted(WORKSPACE_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith('.'):
            file_count = sum(
                1 for f in d.rglob('*')
                if f.is_file() and not _is_hidden_part(f.relative_to(d).parts)
            )
            results.append({"name": d.name, "path": str(d), "files": file_count})
    return results


def delete_workspace(name: str) -> bool:
    """Delete a workspace by name."""
    ws = WORKSPACE_ROOT / name
    if ws.exists() and ws.is_dir() and str(ws).startswith(str(WORKSPACE_ROOT)):
        shutil.rmtree(ws)
        return True
    return False
