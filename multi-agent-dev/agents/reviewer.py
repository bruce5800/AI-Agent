"""Reviewer Agent — tests code and reports issues."""

from pathlib import Path
from agents.tool_agent import ToolAgent

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "reviewer_system.md"


class ReviewerAgent(ToolAgent):
    def __init__(self, workspace: str):
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            name="Reviewer",
            role="Reviewer",
            system_prompt=system_prompt,
            workspace=workspace,
        )
