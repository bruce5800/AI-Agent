"""Architect Agent — designs technical architecture from requirement docs."""

from pathlib import Path
from agents.tool_agent import ToolAgent

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "architect_system.md"


class ArchitectAgent(ToolAgent):
    def __init__(self, workspace: str):
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            name="Architect",
            role="Architect",
            system_prompt=system_prompt,
            workspace=workspace,
        )
