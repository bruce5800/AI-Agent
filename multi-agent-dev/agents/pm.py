"""Product Manager Agent — transforms raw requirements into structured docs."""

from pathlib import Path
from typing import Generator

from agents.tool_agent import ToolAgent
from core.bus import TeamMessage
from core.models import DevMessage, MessageType, Phase
from mcp_servers.filesystem_server import read_file

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

    def handle(self, inbox: list[TeamMessage]) -> Generator:
        """Produce a requirements.md, then request user approval.

        Inbox semantics:
          - msg_type=task           → fresh requirement from User
          - msg_type=task w/ "regenerate" hint → re-do the doc
          - msg_type=escalation     → Reviewer flagged a contradiction; revise
        """
        msg = inbox[-1]
        if msg.msg_type == "escalation":
            prompt = (
                "审查阶段发现需求层面的问题，请重新厘清并更新 requirements.md。\n\n"
                f"反馈内容：\n{msg.content}"
            )
        elif msg.metadata.get("regenerate"):
            prompt = (
                "之前的需求文档被用户拒绝，请根据原始需求重新生成。\n\n"
                f"原始需求：{msg.content}"
            )
        else:
            prompt = f"用户需求：{msg.content}\n\n请分析需求并生成 requirements.md。"

        yield from self.run_with_tools(prompt, Phase.REQUIREMENT)

        doc = read_file(self.workspace, "requirements.md")
        yield TeamMessage(
            sender="PM",
            recipient="User",
            msg_type="approval_request",
            content=doc,
            metadata={"phase": Phase.REQUIREMENT.value, "next_agent": "Architect"},
        )
