"""Unified tool registry — collects all MCP tools and provides per-agent filtering."""

from mcp_servers import filesystem_server, terminal_server, git_server

# Aggregate all tools from all servers
ALL_TOOLS: dict[str, dict] = {}
ALL_TOOLS.update(filesystem_server.TOOLS)
ALL_TOOLS.update(terminal_server.TOOLS)
ALL_TOOLS.update(git_server.TOOLS)

# Per-role tool permissions
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "PM": ["read_file", "write_file", "list_directory"],
    "Architect": ["read_file", "write_file", "list_directory", "run_command"],
    "Programmer": [
        "read_file", "write_file", "list_directory", "search_files",
        "run_command", "git_init", "git_add", "git_commit", "git_status", "git_diff",
    ],
    "Reviewer": ["read_file", "list_directory", "search_files", "run_command"],
}


def get_tools_for_role(role: str) -> dict[str, dict]:
    """Return tool definitions filtered by agent role."""
    allowed = ROLE_PERMISSIONS.get(role, [])
    return {name: tool for name, tool in ALL_TOOLS.items() if name in allowed}


def get_openai_functions_for_role(role: str) -> list[dict]:
    """Return tools in OpenAI function-calling format for a given role."""
    tools = get_tools_for_role(role)
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for name, tool in tools.items()
    ]


def execute_tool(workspace: str, tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments."""
    if tool_name not in ALL_TOOLS:
        return f"Error: unknown tool '{tool_name}'"

    tool = ALL_TOOLS[tool_name]
    func = tool["function"]

    try:
        # All tool functions take workspace as first arg
        return func(workspace, **arguments)
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"
