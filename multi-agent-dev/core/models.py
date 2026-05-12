"""Data models for the multi-agent development system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Phase(str, Enum):
    IDLE = "idle"
    REQUIREMENT = "requirement_analysis"
    DESIGN = "architecture_design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    GIT_COMMIT = "git_commit"
    SUMMARY = "summary"


PHASE_LABELS = {
    Phase.IDLE: "等待开始",
    Phase.REQUIREMENT: "需求分析",
    Phase.DESIGN: "架构设计",
    Phase.IMPLEMENTATION: "编码实现",
    Phase.TESTING: "测试修复",
    Phase.GIT_COMMIT: "Git 提交",
    Phase.SUMMARY: "交付总结",
}


class MessageType(str, Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_CHANGE = "file_change"
    APPROVAL_REQUEST = "approval_request"
    ERROR = "error"
    PHASE_TRANSITION = "phase_transition"
    ROUTE = "route"  # mailbox routing event (TeamMessage → bus)


@dataclass
class DevMessage:
    """A single message in the development flow."""
    speaker: str            # "PM", "Architect", "Programmer", "Reviewer", "System"
    content: str
    phase: Phase
    msg_type: MessageType = MessageType.TEXT
    is_chunk: bool = False  # True = streaming delta token
    metadata: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False


@dataclass
class Artifact:
    """A file produced by an agent."""
    path: str               # Relative path within workspace
    content: str
    created_by: str         # Agent name
    phase: Phase


@dataclass
class ToolCall:
    """Represents a single MCP tool invocation."""
    tool_name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None


@dataclass
class DevState:
    """Full state of a development session."""
    raw_requirement: str = ""
    project_name: str = ""
    workspace_path: str = ""
    current_phase: Phase = Phase.IDLE
    messages: list[DevMessage] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    is_finished: bool = False
    error_count: int = 0
    max_retries: int = 3

    # Documents produced by agents (passed between phases)
    requirement_doc: str = ""
    design_doc: str = ""
    test_output: str = ""
