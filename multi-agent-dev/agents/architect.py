"""Architect Agent — designs technical architecture from requirement docs."""

from pathlib import Path
from typing import Generator

from agents.tool_agent import ToolAgent
from core.bus import TeamMessage
from core.models import Phase
from mcp_servers.filesystem_server import read_file

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

    def handle(self, inbox: list[TeamMessage]) -> Generator:
        """Produce design.md, then request user approval."""
        msg = inbox[-1]
        if msg.metadata.get("regenerate"):
            prompt = (
                "之前的设计被用户拒绝，请重新设计。\n\n"
                f"需求文档：\n{msg.content}"
            )
        else:
            prompt = (
                f"以下是需求文档：\n\n{msg.content}\n\n"
                "请设计技术方案并创建项目目录结构，输出到 design.md。"
            )

        yield from self.run_with_tools(prompt, Phase.DESIGN)

        design = read_file(self.workspace, "design.md")
        yield TeamMessage(
            sender="Architect",
            recipient="User",
            msg_type="approval_request",
            content=design,
            metadata={"phase": Phase.DESIGN.value, "next_agent": "Programmer"},
        )
