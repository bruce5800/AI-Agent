"""Reviewer Agent — tests code and decides where the result goes next."""

import re
from pathlib import Path
from typing import Generator

from agents.tool_agent import ToolAgent
from core.bus import TeamMessage
from core.config import MAX_FIX_RETRIES
from core.models import MessageType, Phase

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "reviewer_system.md"

_RESULT_MARKER = re.compile(r"<<<RESULT:\s*(pass|fail)\s*>>>", re.IGNORECASE)
_ESCALATE_MARKER = re.compile(r"<<<ESCALATE:\s*(\w+)\s*>>>", re.IGNORECASE)


def parse_review(text: str) -> tuple[str, str | None]:
    """Return (verdict, escalate_to). Defaults to ("fail", None) on missing marker."""
    if not text:
        return "fail", None
    result_match = _RESULT_MARKER.findall(text)
    verdict = result_match[-1].lower() if result_match else "fail"
    escalate_match = _ESCALATE_MARKER.findall(text)
    escalate_to = escalate_match[-1] if escalate_match else None
    return verdict, escalate_to


class ReviewerAgent(ToolAgent):
    def __init__(self, workspace: str):
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        super().__init__(
            name="Reviewer",
            role="Reviewer",
            system_prompt=system_prompt,
            workspace=workspace,
        )

    def handle(self, inbox: list[TeamMessage]) -> Generator:
        """Run tests; route based on verdict (and optional escalation marker)."""
        msg = inbox[-1]
        fix_count = msg.metadata.get("fix_count", 0)

        prompt = (
            "请检查项目结构，安装依赖，**用 run_command 实际执行**项目或测试，"
            "并按系统提示词中的格式输出报告。"
            "最后一行必须是 `<<<RESULT: pass>>>` 或 `<<<RESULT: fail>>>`，"
            "如果需要升级到 PM，请在 RESULT 上一行加 `<<<ESCALATE: PM>>>`。"
        )

        review_text = ""
        for ev in self.run_with_tools(prompt, Phase.TESTING):
            yield ev
            if not ev.is_chunk and ev.msg_type == MessageType.TEXT:
                review_text = ev.content

        verdict, escalate_to = parse_review(review_text)

        # --- Dynamic routing: escalation back to PM ---
        if escalate_to and escalate_to.upper() == "PM":
            yield TeamMessage(
                sender="Reviewer",
                recipient="PM",
                msg_type="escalation",
                content=(
                    "审查中发现这不是代码 bug，而是需求层面的矛盾或缺失：\n\n"
                    f"{review_text}"
                ),
                metadata={"phase": Phase.REQUIREMENT.value},
            )
            return

        # --- Normal routing ---
        if verdict == "pass":
            yield TeamMessage(
                sender="Reviewer",
                recipient="Programmer",
                msg_type="task",
                content="测试通过，请 git init/add/commit 提交代码。",
                metadata={"phase": Phase.GIT_COMMIT.value},
            )
            return

        if fix_count >= MAX_FIX_RETRIES:
            yield TeamMessage(
                sender="Reviewer",
                recipient="User",
                msg_type="done",
                content=(
                    f"已重试 {MAX_FIX_RETRIES} 次仍未通过测试，提前交付。\n\n"
                    f"最后一次审查：\n{review_text}"
                ),
                metadata={"phase": Phase.SUMMARY.value, "test_result": "fail"},
            )
            return

        yield TeamMessage(
            sender="Reviewer",
            recipient="Programmer",
            msg_type="fix_request",
            content=review_text,
            metadata={"phase": Phase.TESTING.value, "fix_count": fix_count},
        )
