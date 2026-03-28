"""Product Manager Agent — transforms raw requirements into structured docs."""

from pathlib import Path
from agents.tool_agent import ToolAgent

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "pm_system.md"


class PMAgent(ToolAgent):
    def __init__(self, workspace: str):
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            name="PM",
            role="PM",
            system_prompt=system_prompt,
            workspace=workspace,
        )
