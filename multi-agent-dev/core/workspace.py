"""Workspace management — creation, isolation, cleanup."""

import os
import re
import shutil
from pathlib import Path
from core.config import WORKSPACE_ROOT


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
    """Create a new workspace directory. Returns the absolute path."""
    safe_name = sanitize_name(project_name)
    workspace_path = WORKSPACE_ROOT / safe_name

    # Avoid collision
    if workspace_path.exists():
        i = 1
        while (WORKSPACE_ROOT / f"{safe_name}_{i}").exists():
            i += 1
        workspace_path = WORKSPACE_ROOT / f"{safe_name}_{i}"

    workspace_path.mkdir(parents=True, exist_ok=True)
    return str(workspace_path)


def list_workspaces() -> list[dict]:
    """List all existing workspaces."""
    if not WORKSPACE_ROOT.exists():
        return []
    results = []
    for d in sorted(WORKSPACE_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith('.'):
            file_count = sum(1 for _ in d.rglob('*') if _.is_file())
            results.append({"name": d.name, "path": str(d), "files": file_count})
    return results


def delete_workspace(name: str) -> bool:
    """Delete a workspace by name."""
    ws = WORKSPACE_ROOT / name
    if ws.exists() and ws.is_dir() and str(ws).startswith(str(WORKSPACE_ROOT)):
        shutil.rmtree(ws)
        return True
    return False
