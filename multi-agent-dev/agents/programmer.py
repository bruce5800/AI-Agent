"""Programmer Agent — writes code based on design documents."""

from pathlib import Path
from agents.tool_agent import ToolAgent

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "programmer_system.md"


class ProgrammerAgent(ToolAgent):
    def __init__(self, workspace: str):
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            name="Programmer",
            role="Programmer",
            system_prompt=system_prompt,
            workspace=workspace,
        )
