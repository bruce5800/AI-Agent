"""DevEngine — orchestrates the multi-agent development flow.

Uses a generator pattern (like the debate engine) to yield DevMessage
objects for real-time streaming in the Streamlit UI.
"""

import re
from typing import Generator

from agents.pm import PMAgent
from agents.architect import ArchitectAgent
from agents.programmer import ProgrammerAgent
from agents.reviewer import ReviewerAgent
from core.models import DevMessage, DevState, Phase, MessageType
from core.workspace import create_workspace, derive_project_slug
from mcp_servers.filesystem_server import read_file, list_directory


_RESULT_MARKER = re.compile(r"<<<RESULT:\s*(pass|fail)\s*>>>", re.IGNORECASE)


def _parse_review_result(text: str) -> str:
    """Parse the structured `<<<RESULT: pass|fail>>>` marker.

    Returns "pass" or "fail". If no marker is present, defaults to "fail"
    (safer — forces another fix loop iteration rather than a false success).
    """
    if not text:
        return "fail"
    matches = _RESULT_MARKER.findall(text)
    if not matches:
        return "fail"
    return matches[-1].lower()


class DevEngine:
    """Orchestrates the full development process across 7 phases."""

    def __init__(self, requirement: str):
        self.state = DevState(raw_requirement=requirement)

    def _phase_msg(self, phase: Phase, content: str) -> DevMessage:
        """Create a system phase transition message."""
        return DevMessage(
            speaker="System",
            content=content,
            phase=phase,
            msg_type=MessageType.PHASE_TRANSITION,
        )

    def _approval_msg(self, phase: Phase, content: str) -> DevMessage:
        """Create an approval request message."""
        return DevMessage(
            speaker="System",
            content=content,
            phase=phase,
            msg_type=MessageType.APPROVAL_REQUEST,
            requires_approval=True,
        )

    def run(self) -> Generator[DevMessage, str | None, None]:
        """Run the full development pipeline.

        This is a generator that yields DevMessage objects.
        At approval gates, it yields an approval_request message and
        expects the caller to send() the approval result:
          - "approved" to continue
          - "edit:..." to pass edited content
          - "regenerate" to re-run the phase

        Yields:
            DevMessage objects for UI rendering
        """

        # === Phase 1: Create workspace ===
        self.state.current_phase = Phase.REQUIREMENT
        yield self._phase_msg(Phase.REQUIREMENT, "开始需求分析...")

        # Derive a meaningful workspace name from the user's requirement
        # (rather than the placeholder "temp_project"). PM may write a
        # nicer name into requirements.md; we surface it in the summary
        # but don't rename the dir to avoid mid-flight path churn.
        project_slug = derive_project_slug(self.state.raw_requirement)
        workspace = create_workspace(project_slug)
        self.state.project_name = project_slug
        self.state.workspace_path = workspace

        # === Phase 2: Requirement Analysis (PM) ===
        pm = PMAgent(workspace)
        prompt = f"用户需求：{self.state.raw_requirement}\n\n请分析需求并生成需求文档。"

        for msg in pm.run_with_tools(prompt, Phase.REQUIREMENT):
            self.state.messages.append(msg)
            yield msg

        # Read the generated requirement doc
        self.state.requirement_doc = read_file(workspace, "requirements.md")

        # Approval gate
        approval = yield self._approval_msg(
            Phase.REQUIREMENT,
            "需求文档已生成，请审阅。",
        )
        if approval and approval.startswith("edit:"):
            self.state.requirement_doc = approval[5:]

        # === Phase 3: Architecture Design (Architect) ===
        self.state.current_phase = Phase.DESIGN
        yield self._phase_msg(Phase.DESIGN, "开始架构设计...")

        architect = ArchitectAgent(workspace)
        prompt = (
            f"以下是需求文档：\n\n{self.state.requirement_doc}\n\n"
            f"请设计技术方案并创建项目目录结构。"
        )

        for msg in architect.run_with_tools(prompt, Phase.DESIGN):
            self.state.messages.append(msg)
            yield msg

        # Read the generated design doc
        self.state.design_doc = read_file(workspace, "design.md")

        # Approval gate
        approval = yield self._approval_msg(
            Phase.DESIGN,
            "架构设计已完成，请审阅。",
        )
        if approval and approval.startswith("edit:"):
            self.state.design_doc = approval[5:]

        # === Phase 4: Implementation (Programmer) ===
        self.state.current_phase = Phase.IMPLEMENTATION
        yield self._phase_msg(Phase.IMPLEMENTATION, "开始编码实现...")

        programmer = ProgrammerAgent(workspace)
        prompt = (
            f"以下是设计文档：\n\n{self.state.design_doc}\n\n"
            f"请按照设计文档逐文件编写代码。"
        )

        for msg in programmer.run_with_tools(prompt, Phase.IMPLEMENTATION):
            self.state.messages.append(msg)
            yield msg

        # === Phase 5: Testing & Fix Loop ===
        self.state.current_phase = Phase.TESTING
        yield self._phase_msg(Phase.TESTING, "开始测试验证...")

        reviewer = ReviewerAgent(workspace)
        self.state.error_count = 0

        while self.state.error_count < self.state.max_retries:
            review_prompt = (
                "请检查项目结构，安装依赖，**用 run_command 实际执行**项目或测试，"
                "并按系统提示词中的格式输出报告，**最后一行必须是 "
                "`<<<RESULT: pass>>>` 或 `<<<RESULT: fail>>>`**。"
            )

            review_text = ""
            for msg in reviewer.run_with_tools(review_prompt, Phase.TESTING):
                self.state.messages.append(msg)
                yield msg
                if not msg.is_chunk and msg.msg_type == MessageType.TEXT:
                    review_text = msg.content

            self.state.test_output = review_text

            # Structured pass/fail: parse the trailing <<<RESULT: ...>>> marker.
            # If marker is missing, default to "fail" — safer than a false pass.
            verdict = _parse_review_result(review_text)
            if verdict == "pass":
                break

            # Tests failed — programmer fixes
            self.state.error_count += 1
            if self.state.error_count >= self.state.max_retries:
                yield DevMessage(
                    speaker="System",
                    content=f"已重试 {self.state.max_retries} 次，仍有问题。请手动检查。",
                    phase=Phase.TESTING,
                    msg_type=MessageType.ERROR,
                )
                break

            yield self._phase_msg(
                Phase.TESTING,
                f"发现问题，程序员修复中...（第 {self.state.error_count} 次修复）",
            )

            fix_prompt = (
                f"测试/审查发现以下问题：\n\n{review_text}\n\n"
                f"请读取相关文件，修复代码。"
            )
            for msg in programmer.run_with_tools(fix_prompt, Phase.TESTING):
                self.state.messages.append(msg)
                yield msg

        # === Phase 6: Git Commit ===
        self.state.current_phase = Phase.GIT_COMMIT
        yield self._phase_msg(Phase.GIT_COMMIT, "提交代码到 Git...")

        git_prompt = "请初始化 git 仓库，添加所有文件并提交，commit 信息为 'Initial commit: {project}'。"
        for msg in programmer.run_with_tools(git_prompt, Phase.GIT_COMMIT):
            self.state.messages.append(msg)
            yield msg

        # === Phase 7: Summary ===
        self.state.current_phase = Phase.SUMMARY
        yield self._phase_msg(Phase.SUMMARY, "生成项目交付总结...")

        # Get final file tree
        file_tree = list_directory(workspace)

        summary = (
            f"## 项目交付完成\n\n"
            f"**项目路径：** `{workspace}`\n\n"
            f"**文件结构：**\n```\n{file_tree}\n```\n\n"
            f"**测试结果：** {self.state.test_output[:200] if self.state.test_output else '未执行测试'}\n\n"
            f"**修复次数：** {self.state.error_count}\n"
        )

        yield DevMessage(
            speaker="System",
            content=summary,
            phase=Phase.SUMMARY,
            msg_type=MessageType.TEXT,
        )

        self.state.is_finished = True
