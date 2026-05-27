"""DevEngine — bus-driven router for the multi-agent development flow.

The old version was a hard-coded 7-phase pipeline:
    PM → [approve] → Architect → [approve] → Programmer → Reviewer ↔ Programmer → git → summary

That made it impossible for Reviewer to bounce a requirements problem back to
PM, or for the order to change at all without editing this file.

This version is a **router loop** over an in-memory ``MessageBus``. Each agent
implements ``handle(inbox)`` which decides what to do and where to send the
result next (via ``TeamMessage``). The engine just:

1. drain the next non-empty inbox (User first, then PM/Architect/Programmer/Reviewer)
2. dispatch to that agent
3. yield UI events; route any ``TeamMessage`` back through the bus
4. if it's an ``approval_request`` to ``User``, pause the generator at an
   approval gate (same ``yield approval_msg`` mechanism the UI already speaks)
5. terminate on a ``done`` message

Adding a dynamic edge — e.g. Reviewer → PM escalation — is now just a matter
of having Reviewer emit a ``TeamMessage(recipient="PM", msg_type="escalation")``.
No engine changes needed.
"""

import os
from typing import Generator

from agents.pm import PMAgent
from agents.architect import ArchitectAgent
from agents.programmer import ProgrammerAgent
from agents.reviewer import ReviewerAgent
from core.bus import MessageBus, TeamMessage
from core.models import DevMessage, DevState, MessageType, Phase
from core.workspace import create_workspace, derive_project_slug
from core.worktree import WorktreeSession
from mcp_servers.filesystem_server import list_directory, write_file


# Hard cap so a buggy escalation loop can't run forever.
MAX_BUS_STEPS = 40


class DevEngine:
    """Drives a MessageBus of cooperating agents until the pipeline terminates."""

    def __init__(self, requirement: str):
        self.state = DevState(raw_requirement=requirement)
        self.bus = MessageBus()
        self.agents: dict = {}
        self._workspace: str = ""
        self.worktree: WorktreeSession | None = None  # set in run()

    # ----- DevMessage helpers (unchanged from previous version) -----

    def _phase_msg(self, phase: Phase, content: str) -> DevMessage:
        return DevMessage(
            speaker="System",
            content=content,
            phase=phase,
            msg_type=MessageType.PHASE_TRANSITION,
        )

    def _approval_msg(self, phase: Phase, content: str) -> DevMessage:
        return DevMessage(
            speaker="System",
            content=content,
            phase=phase,
            msg_type=MessageType.APPROVAL_REQUEST,
            requires_approval=True,
        )

    def _route_msg(self, tm: TeamMessage, phase: Phase) -> DevMessage:
        """Render a peer-to-peer routing event in the UI feed."""
        return DevMessage(
            speaker="System",
            content=f"📨 {tm.sender} → {tm.recipient} ({tm.msg_type})",
            phase=phase,
            msg_type=MessageType.ROUTE,
            metadata={"team_message": tm},
        )

    # ----- Main router loop -----

    def run(self) -> Generator[DevMessage, str | None, None]:
        # --- Bootstrap workspace + agents ---
        self.state.current_phase = Phase.REQUIREMENT
        yield self._phase_msg(Phase.REQUIREMENT, "开始需求分析...")

        slug = derive_project_slug(self.state.raw_requirement)
        self._workspace = create_workspace(slug)
        self.state.project_name = slug
        self.state.workspace_path = self._workspace
        self.worktree = WorktreeSession(self._workspace)

        self.agents = {
            "PM": PMAgent(self._workspace),
            "Architect": ArchitectAgent(self._workspace),
            "Programmer": ProgrammerAgent(self._workspace),
            "Reviewer": ReviewerAgent(self._workspace),
        }

        # Kick off: User assigns initial task to PM.
        self.bus.send(TeamMessage(
            sender="User",
            recipient="PM",
            msg_type="task",
            content=self.state.raw_requirement,
            metadata={"phase": Phase.REQUIREMENT.value},
        ))

        # Priority queue: handle User approvals first (so UI doesn't queue up
        # peer chatter behind a pending approval), then agents in pipeline order.
        priority = ["User", "PM", "Architect", "Programmer", "Reviewer"]

        for _step in range(MAX_BUS_STEPS):
            recipient = self.bus.next_pending(priority)
            if recipient is None:
                yield self._phase_msg(Phase.SUMMARY, "总线已空，流程结束。")
                break

            if recipient == "User":
                done = yield from self._handle_user_inbox()
                if done:
                    break
                continue

            yield from self._dispatch_agent(recipient)
        else:
            yield DevMessage(
                speaker="System",
                content=f"达到最大调度步数 {MAX_BUS_STEPS}，强制结束。",
                phase=Phase.SUMMARY,
                msg_type=MessageType.ERROR,
            )

        yield from self._emit_summary()
        self.state.is_finished = True

    # ----- Inbox-specific handlers -----

    def _handle_user_inbox(self) -> Generator[DevMessage, str | None, bool]:
        """Process messages addressed to User. Returns True if pipeline is done."""
        for m in self.bus.drain("User"):
            phase = Phase(m.metadata.get("phase", Phase.IDLE.value))
            self.state.current_phase = phase

            if m.msg_type == "done":
                # Wrap up: settle any active fix worktree, then summarize.
                yield from self._finalize_repo(m.metadata.get("test_result", ""))
                yield self._phase_msg(Phase.SUMMARY, "✅ 已交付。")
                self.state.test_output = m.metadata.get("test_result", "")
                return True

            if m.msg_type != "approval_request":
                # Unknown message to User — surface it but keep going.
                yield DevMessage(
                    speaker="System",
                    content=f"(忽略未知消息: {m.msg_type})",
                    phase=phase,
                    msg_type=MessageType.ERROR,
                )
                continue

            # --- Approval gate ---
            next_agent = m.metadata.get("next_agent", "")
            approval = yield self._approval_msg(phase, m.content)

            edited_content = m.content
            user_edited = False
            if approval and approval.startswith("edit:"):
                edited_content = approval[5:]
                approval_kind = "approved"
                user_edited = edited_content != m.content
            else:
                approval_kind = approval or "approved"

            # Persist user edits back to the workspace file (e.g. requirements.md
            # / design.md), so a downstream agent that reads from disk — rather
            # than from the bus message content — sees the approved version.
            if user_edited:
                target = {
                    Phase.REQUIREMENT: "requirements.md",
                    Phase.DESIGN: "design.md",
                }.get(phase)
                if target and self._workspace:
                    try:
                        write_file(self._workspace, target, edited_content)
                        yield self._phase_msg(
                            phase, f"📝 用户编辑了 {target}（已写回 workspace）"
                        )
                    except Exception as e:
                        yield DevMessage(
                            speaker="System",
                            content=f"(无法写入编辑后的 {target}: {e})",
                            phase=phase,
                            msg_type=MessageType.ERROR,
                        )

            if approval_kind == "regenerate":
                # Send it back to the sender, marked regenerate.
                self.bus.send(TeamMessage(
                    sender="User",
                    recipient=m.sender,
                    msg_type="task",
                    content=self.state.raw_requirement,
                    metadata={"phase": phase.value, "regenerate": True},
                ))
            else:
                # Approved — pass the (possibly edited) content to next_agent.
                if not next_agent:
                    yield DevMessage(
                        speaker="System",
                        content=f"(approval_request 缺少 next_agent，丢弃)",
                        phase=phase,
                        msg_type=MessageType.ERROR,
                    )
                    continue
                self.bus.send(TeamMessage(
                    sender="User",
                    recipient=next_agent,
                    msg_type="task",
                    content=edited_content,
                    metadata={"phase": _next_phase_for(next_agent).value},
                ))

            # Stash for summary
            if phase == Phase.REQUIREMENT:
                self.state.requirement_doc = edited_content
            elif phase == Phase.DESIGN:
                self.state.design_doc = edited_content

        return False

    def _dispatch_agent(self, name: str) -> Generator[DevMessage, None, None]:
        """Run one agent against its drained inbox.

        Wraps the agent's ``handle()`` with three git lifecycle hooks:

        1. **Pre-dispatch fix-mode entry** — if a ``fix_request`` is in the
           inbox and we have no active worktree, branch one off main's HEAD
           and redirect the agent's workspace to it.
        2. **Workspace redirection** — while a fix worktree is active,
           Programmer/Reviewer operate on the worktree, not main.
        3. **Post-dispatch hooks** — auto-commit on main after a successful
           initial implementation; auto-commit in the worktree after each fix
           attempt; discard the worktree if Reviewer escalates to PM.
        """
        inbox = self.bus.drain(name)
        if not inbox:
            return

        phase = Phase(inbox[-1].metadata.get("phase", Phase.IDLE.value))
        self.state.current_phase = phase
        yield self._phase_msg(phase, f"→ {name} 处理 {len(inbox)} 条消息")

        # --- Pre-dispatch: enter fix mode if a fix_request just arrived ---
        is_fix_request = any(m.msg_type == "fix_request" for m in inbox)
        if (
            is_fix_request
            and self.worktree is not None
            and not self.worktree.is_active()
        ):
            yield from self._enter_fix_mode()

        agent = self.agents[name]

        # --- Workspace redirection ---
        original_ws = agent.workspace
        if (
            self.worktree is not None
            and self.worktree.is_active()
            and name in ("Programmer", "Reviewer")
        ):
            agent.workspace = self.worktree.path
            yield self._phase_msg(
                phase, f"🔀 {name} workspace 切换到 worktree: {self.worktree.path}"
            )

        pre_audit_len = len(self.bus.audit)
        try:
            for output in agent.handle(inbox):
                if isinstance(output, DevMessage):
                    self.state.messages.append(output)
                    yield output
                elif isinstance(output, TeamMessage):
                    self.bus.send(output)
                    yield self._route_msg(output, phase)
        finally:
            agent.workspace = original_ws

        new_msgs = self.bus.audit[pre_audit_len:]

        # --- Post-dispatch hooks ---

        # Programmer just finished initial implementation → commit on main.
        if name == "Programmer" and phase == Phase.IMPLEMENTATION:
            assert self.worktree is not None
            yield self._phase_msg(
                Phase.IMPLEMENTATION,
                "📦 " + self.worktree.init_main(),
            )
            yield self._phase_msg(
                Phase.IMPLEMENTATION,
                "📦 " + self.worktree.commit_main("feat: initial implementation"),
            )

        # Programmer just finished a fix attempt → commit on the fix branch.
        elif (
            name == "Programmer"
            and phase == Phase.TESTING
            and self.worktree is not None
            and self.worktree.is_active()
        ):
            fix_count = inbox[-1].metadata.get("fix_count", 0) + 1
            msg = self.worktree.commit_attempt(f"fix: attempt {fix_count}")
            yield self._phase_msg(Phase.TESTING, f"📦 worktree: {msg}")

        # Reviewer escalated to PM → invalidate the speculative branch.
        elif name == "Reviewer" and self.worktree is not None and self.worktree.is_active():
            had_escalation = any(
                m.recipient == "PM" and m.msg_type == "escalation" for m in new_msgs
            )
            if had_escalation:
                yield from self._exit_fix_mode(merge=False, reason="Reviewer 升级到 PM")

    # ----- Worktree lifecycle helpers -----

    def _enter_fix_mode(self) -> Generator[DevMessage, None, None]:
        """Branch a worktree off main HEAD; subsequent Programmer/Reviewer
        dispatches operate on it until exit."""
        assert self.worktree is not None
        msg = self.worktree.start()
        yield self._phase_msg(Phase.TESTING, f"🌿 进入 fix 模式: {msg}")

    def _exit_fix_mode(
        self, merge: bool, reason: str = ""
    ) -> Generator[DevMessage, None, None]:
        """Either squash-merge or discard the active worktree."""
        assert self.worktree is not None
        if not self.worktree.is_active():
            return
        if merge:
            out = self.worktree.merge_to_main(
                "fix: accepted speculative changes (squashed)"
            )
            yield self._phase_msg(Phase.GIT_COMMIT, f"✅ 合并 fix worktree: {out}")
        else:
            out = self.worktree.discard()
            reason_suffix = f" ({reason})" if reason else ""
            yield self._phase_msg(
                Phase.GIT_COMMIT, f"🗑️  丢弃 fix worktree{reason_suffix}: {out}"
            )

    def _finalize_repo(
        self, test_result: str
    ) -> Generator[DevMessage, None, None]:
        """Called on User `done` arrival. Settle any active worktree."""
        if self.worktree is None or not self.worktree.is_active():
            return
        if test_result == "pass":
            yield from self._exit_fix_mode(merge=True)
        else:
            yield from self._exit_fix_mode(merge=False, reason=f"test_result={test_result}")

    def _emit_summary(self) -> Generator[DevMessage, None, None]:
        if not os.path.isdir(self._workspace):
            return
        try:
            tree = list_directory(self._workspace)
        except Exception as e:
            tree = f"(无法列出文件: {e})"

        # Git history if we managed to commit anything
        git_log = ""
        if self.worktree is not None and self.worktree.is_main_repo():
            import subprocess
            r = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=self._workspace,
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                git_log = r.stdout.strip() or "(no commits)"

        summary = (
            f"## 项目交付\n\n"
            f"**workspace：** `{self._workspace}`\n\n"
            f"**文件结构：**\n```\n{tree}\n```\n\n"
            f"**总线消息总数：** {len(self.bus.audit)}\n"
        )
        if git_log:
            summary += f"\n**Git 历史：**\n```\n{git_log}\n```\n"
        yield DevMessage(
            speaker="System",
            content=summary,
            phase=Phase.SUMMARY,
            msg_type=MessageType.TEXT,
        )


def _next_phase_for(agent_name: str) -> Phase:
    """Map a recipient agent to the phase its task represents.

    Kept tiny on purpose — adding a new agent only requires adding one row.
    """
    return {
        "PM": Phase.REQUIREMENT,
        "Architect": Phase.DESIGN,
        "Programmer": Phase.IMPLEMENTATION,
        "Reviewer": Phase.TESTING,
    }.get(agent_name, Phase.IDLE)
