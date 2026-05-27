"""Todo MCP tool — structured task list with status tracking.

Inspired by docs/s03 (TodoWrite). The semantic contract is:

- Each ``todo_write`` call **replaces** the entire list. The agent thinks in
  terms of the whole plan, not per-item diffs. (This is the same pattern as
  Claude Code's TodoWrite.)
- Each todo is ``{content, status, activeForm?}`` where ``status`` is one of
  ``pending`` / ``in_progress`` / ``completed``.
- The list is persisted to ``<workspace>/.todos.json`` so the UI can read it
  out-of-band (or re-render on Streamlit script reruns).

Value: long-running multi-file work (typical Programmer agent behavior) feels
opaque without this — the user sees streaming text but no sense of "how far
along are we?". A live checklist gives that signal cheaply.
"""

import json
import os

_VALID_STATUS = {"pending", "in_progress", "completed"}


def _resolve_todos_path(workspace: str) -> str:
    return os.path.join(workspace, ".todos.json")


def todo_write(workspace: str, todos: list) -> str:
    """Replace the project's todo list. Returns a short summary for the LLM."""
    if not isinstance(todos, list):
        return f"Error: todos must be a list, got {type(todos).__name__}"

    cleaned = []
    for i, t in enumerate(todos):
        if not isinstance(t, dict):
            return f"Error: todos[{i}] must be a dict"
        content = (t.get("content") or "").strip()
        if not content:
            return f"Error: todos[{i}] is missing 'content'"
        status = t.get("status", "pending")
        if status not in _VALID_STATUS:
            return (
                f"Error: todos[{i}] status='{status}' is not one of "
                f"{sorted(_VALID_STATUS)}"
            )
        item = {"content": content, "status": status}
        active_form = (t.get("activeForm") or "").strip()
        if active_form:
            item["activeForm"] = active_form
        cleaned.append(item)

    path = _resolve_todos_path(workspace)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    counts = {"pending": 0, "in_progress": 0, "completed": 0}
    for t in cleaned:
        counts[t["status"]] += 1
    return (
        f"Saved {len(cleaned)} todos "
        f"({counts['completed']} ✅ / {counts['in_progress']} 🔄 / {counts['pending']} ⏳)."
    )


def load_todos(workspace: str) -> list:
    """Read the current todos from disk. Returns ``[]`` if file is missing/invalid."""
    path = _resolve_todos_path(workspace)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


TOOLS = {
    "todo_write": {
        "function": todo_write,
        "description": (
            "Maintain a structured task list with status tracking. Pass the "
            "FULL list each time — this call replaces the existing list. "
            "Call once at the start to plan your work, then call again to "
            "mark items in_progress / completed as you proceed. The user "
            "sees a live progress checklist in the sidebar. "
            "Each item: {content, status, activeForm?}. "
            "status must be one of: pending, in_progress, completed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "Full list of todos (replaces existing)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "What this todo is about (imperative form)",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                            "activeForm": {
                                "type": "string",
                                "description": "Optional present-continuous form for display while in_progress (e.g. 'Writing tests')",
                            },
                        },
                        "required": ["content", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    },
}
