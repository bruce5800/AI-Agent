"""Programmer Agent — writes code, fixes bugs, and commits to git."""

from pathlib import Path
from typing import Generator

from agents.tool_agent import ToolAgent
from core.bus import TeamMessage
from core.models import Phase

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

    def handle(self, inbox: list[TeamMessage]) -> Generator:
        """Three modes, dispatched by msg_type + phase metadata:

        - implement: design.md → code
        - fix:       Reviewer's report → patched code
        - commit:    git init/add/commit
        Each hands off to the next agent via a TeamMessage.
        """
        msg = inbox[-1]
        phase_str = msg.metadata.get("phase", "")

        if msg.msg_type == "fix_request":
            prompt = (
                f"测试/审查发现以下问题：\n\n{msg.content}\n\n"
                "请读取相关文件，修复代码。修复完成后无需再做其它说明。"
            )
            yield from self.run_with_tools(prompt, Phase.TESTING)

            fix_count = msg.metadata.get("fix_count", 0) + 1
            yield TeamMessage(
                sender="Programmer",
                recipient="Reviewer",
                msg_type="task",
                content="已修复，请重新审查并执行测试。",
                metadata={"phase": Phase.TESTING.value, "fix_count": fix_count},
            )
            return

        # NOTE: There is no GIT_COMMIT branch anymore. The engine handles all
        # git lifecycle deterministically (initial commit after impl; squash-
        # merge or discard of the fix worktree based on Reviewer's verdict).
        # Programmer only ever does *code*; the engine owns the repo.

        # Default: initial implementation
        prompt = (
            f"以下是设计文档：\n\n{msg.content}\n\n"
            "请按照设计文档逐文件编写代码。"
        )
        yield from self.run_with_tools(prompt, Phase.IMPLEMENTATION)

        yield TeamMessage(
            sender="Programmer",
            recipient="Reviewer",
            msg_type="task",
            content="代码实现完成，请审查并执行测试。",
            metadata={"phase": Phase.TESTING.value, "fix_count": 0},
        )
