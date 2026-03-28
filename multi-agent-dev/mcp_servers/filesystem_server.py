"""Filesystem MCP tools — read, write, list, search files within workspace."""

import os
from pathlib import Path


def _resolve_path(workspace: str, relative_path: str) -> str:
    """Resolve and validate path is within workspace."""
    ws = Path(workspace).resolve()
    target = (ws / relative_path).resolve()
    if not str(target).startswith(str(ws)):
        raise ValueError(f"Path traversal blocked: {relative_path}")
    return str(target)


def read_file(workspace: str, path: str) -> str:
    """Read the contents of a file. Path is relative to workspace root."""
    full_path = _resolve_path(workspace, path)
    if not os.path.isfile(full_path):
        return f"Error: file not found: {path}"
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(workspace: str, path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    full_path = _resolve_path(workspace, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written {len(content)} chars to {path}"


def list_directory(workspace: str, path: str = ".") -> str:
    """List contents of a directory as a tree."""
    full_path = _resolve_path(workspace, path)
    if not os.path.isdir(full_path):
        return f"Error: directory not found: {path}"

    lines = []
    ws_root = Path(workspace).resolve()

    def _tree(dir_path: Path, prefix: str = ""):
        entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        for i, entry in enumerate(entries):
            if entry.name.startswith(".") and entry.name != ".gitignore":
                continue
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                _tree(entry, prefix + extension)

    lines.append(str(Path(full_path).relative_to(ws_root)) if full_path != str(ws_root) else ".")
    _tree(Path(full_path))
    return "\n".join(lines)


def search_files(workspace: str, pattern: str, path: str = ".") -> str:
    """Search for files matching a glob pattern."""
    full_path = _resolve_path(workspace, path)
    matches = list(Path(full_path).rglob(pattern))
    ws_root = Path(workspace).resolve()
    results = [str(m.relative_to(ws_root)) for m in matches if m.is_file()]
    if not results:
        return f"No files matching '{pattern}'"
    return "\n".join(results)


# Tool definitions for registry
TOOLS = {
    "read_file": {
        "function": read_file,
        "description": "Read the contents of a file. Path is relative to workspace root.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
            },
            "required": ["path"],
        },
    },
    "write_file": {
        "function": write_file,
        "description": "Write content to a file. Creates parent directories if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "File content to write"},
            },
            "required": ["path", "content"],
        },
    },
    "list_directory": {
        "function": list_directory,
        "description": "List contents of a directory as a tree structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative directory path, defaults to '.'"},
            },
            "required": [],
        },
    },
    "search_files": {
        "function": search_files,
        "description": "Search for files matching a glob pattern.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', '**/*.js')"},
                "path": {"type": "string", "description": "Directory to search in, defaults to '.'"},
            },
            "required": ["pattern"],
        },
    },
}
