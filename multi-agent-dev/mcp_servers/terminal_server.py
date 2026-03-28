"""Terminal MCP tools — execute shell commands within workspace."""

import subprocess
from core.config import COMMAND_DENYLIST, COMMAND_TIMEOUT


def _check_command_safety(command: str) -> str | None:
    """Return error message if command is denied, else None."""
    cmd_lower = command.lower().strip()
    for denied in COMMAND_DENYLIST:
        if denied in cmd_lower:
            return f"Error: command blocked for safety: '{denied}'"
    return None


def run_command(workspace: str, command: str, timeout: int = COMMAND_TIMEOUT) -> str:
    """Run a shell command in the workspace directory.

    Returns stdout + stderr. Timeout defaults to 30 seconds.
    """
    safety_error = _check_command_safety(command)
    if safety_error:
        return safety_error

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=min(timeout, 120),  # Hard cap at 120s
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
        "description": "Run a shell command in the workspace directory. Returns stdout + stderr.",
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
