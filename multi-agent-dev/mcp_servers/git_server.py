"""Git MCP tools — version control operations within workspace."""

import subprocess


def _git(workspace: str, *args: str) -> str:
    """Run a git command in the workspace."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += ("\n" + result.stderr.strip()) if output else result.stderr.strip()
        return output if output else "(no output)"
    except Exception as e:
        return f"Error: {str(e)}"


def git_init(workspace: str) -> str:
    """Initialize a git repository in the workspace."""
    return _git(workspace, "init")


def git_add(workspace: str, files: str = ".") -> str:
    """Stage files for commit."""
    return _git(workspace, "add", files)


def git_commit(workspace: str, message: str) -> str:
    """Create a commit with the given message."""
    return _git(workspace, "commit", "-m", message)


def git_status(workspace: str) -> str:
    """Show git status."""
    return _git(workspace, "status", "--short")


def git_diff(workspace: str) -> str:
    """Show staged and unstaged diffs."""
    staged = _git(workspace, "diff", "--cached")
    unstaged = _git(workspace, "diff")
    parts = []
    if staged and staged != "(no output)":
        parts.append(f"=== Staged ===\n{staged}")
    if unstaged and unstaged != "(no output)":
        parts.append(f"=== Unstaged ===\n{unstaged}")
    return "\n\n".join(parts) if parts else "(no changes)"


TOOLS = {
    "git_init": {
        "function": git_init,
        "description": "Initialize a git repository in the workspace.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "git_add": {
        "function": git_add,
        "description": "Stage files for commit.",
        "parameters": {
            "type": "object",
            "properties": {
                "files": {"type": "string", "description": "Files to stage, defaults to '.' (all)"},
            },
            "required": [],
        },
    },
    "git_commit": {
        "function": git_commit,
        "description": "Create a commit with the given message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
            },
            "required": ["message"],
        },
    },
    "git_status": {
        "function": git_status,
        "description": "Show git status.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "git_diff": {
        "function": git_diff,
        "description": "Show staged and unstaged diffs.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}
