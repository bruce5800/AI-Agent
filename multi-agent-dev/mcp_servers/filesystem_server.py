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


# Read defaults: matches Claude Code's Read tool semantics — line-based
# windowing keeps the prompt manageable on large files while letting an agent
# page through via `offset` if it really needs more.
_READ_DEFAULT_LIMIT = 2000     # lines per call (default)
_READ_MAX_LIMIT = 10000        # absolute upper bound (defends against silly limit=999999)
_READ_MAX_BYTES = 200_000      # final byte cap (defends against pathological single-line huge files)


def read_file(
    workspace: str,
    path: str,
    offset: int = 0,
    limit: int = _READ_DEFAULT_LIMIT,
) -> str:
    """Read a file with line-based windowing.

    Args:
        path:   file path relative to workspace root
        offset: 0-based starting line (default 0)
        limit:  max lines to read (default 2000, hard-capped at 10000)

    Returns:
        File contents. If truncated, a `…[truncated at line X of Y;
        call read_file again with offset=X]` tail tells the agent how to
        continue. A 200KB byte ceiling is also enforced after line slicing
        for pathological single-line huge files.
    """
    full_path = _resolve_path(workspace, path)
    if not os.path.isfile(full_path):
        return f"Error: file not found: {path}"

    # Defensive clamping — agents sometimes hallucinate huge limits
    limit = max(1, min(int(limit or _READ_DEFAULT_LIMIT), _READ_MAX_LIMIT))
    offset = max(0, int(offset or 0))

    with open(full_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    total = len(lines)

    if offset >= total and total > 0:
        return f"(EOF reached; file has {total} lines, offset={offset} is past the end)"

    selected = lines[offset:offset + limit]
    content = "".join(selected)
    end_line = offset + len(selected)

    # Header when we're not starting at the top
    if offset > 0:
        content = f"[showing lines {offset}-{end_line - 1} of {total}]\n\n" + content

    # Trailing hint when there's more
    if end_line < total:
        content += (
            f"\n\n…[truncated at line {end_line} of {total}; "
            f"call read_file again with offset={end_line} to continue]"
        )

    # Final byte cap: catches single-line files or unicode-heavy content that
    # blew through 200KB despite the line limit.
    encoded_len = len(content.encode("utf-8"))
    if encoded_len > _READ_MAX_BYTES:
        truncated = content.encode("utf-8")[:_READ_MAX_BYTES].decode(
            "utf-8", errors="ignore"
        )
        content = (
            truncated
            + f"\n\n…[byte cap {_READ_MAX_BYTES} reached (original {encoded_len} bytes); "
            f"narrow the range with offset/limit to see more]"
        )

    return content


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
        "description": (
            "Read a file with line-based windowing. By default reads the first "
            "2000 lines. For larger files, the response ends with a hint like "
            "'…[truncated at line X of Y; call read_file again with offset=X]'; "
            "use the returned offset to continue paging. A 200KB byte cap is "
            "also enforced as a final safeguard."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "offset": {
                    "type": "integer",
                    "description": "0-based starting line (default 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max lines to read (default 2000, hard-capped at 10000)",
                },
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
