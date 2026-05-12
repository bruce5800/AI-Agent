"""Reusable Streamlit rendering components."""

import streamlit as st
from core.models import DevMessage, Phase, MessageType, PHASE_LABELS

PHASE_ICONS = {
    Phase.IDLE: "⏳",
    Phase.REQUIREMENT: "📋",
    Phase.DESIGN: "🏗️",
    Phase.IMPLEMENTATION: "💻",
    Phase.TESTING: "🧪",
    Phase.GIT_COMMIT: "🔀",
    Phase.SUMMARY: "📦",
}

SPEAKER_CONFIG = {
    "PM": {"icon": "📋", "tag_class": "tag-pm", "label": "产品经理"},
    "Architect": {"icon": "🏗️", "tag_class": "tag-architect", "label": "架构师"},
    "Programmer": {"icon": "💻", "tag_class": "tag-programmer", "label": "程序员"},
    "Reviewer": {"icon": "🧪", "tag_class": "tag-reviewer", "label": "审查员"},
    "System": {"icon": "⚙️", "tag_class": "tag-system", "label": "系统"},
}


def render_phase_divider(phase: Phase):
    """Render a centered phase divider."""
    icon = PHASE_ICONS.get(phase, "▪️")
    label = PHASE_LABELS.get(phase, str(phase))
    st.markdown(
        f'<div class="phase-divider"><span class="phase-divider-text">{icon} {label}</span></div>',
        unsafe_allow_html=True,
    )


def render_message(msg: DevMessage):
    """Render a complete message based on its type."""
    if msg.msg_type == MessageType.PHASE_TRANSITION:
        return  # Phase transitions are handled by dividers

    cfg = SPEAKER_CONFIG.get(msg.speaker, SPEAKER_CONFIG["System"])

    if msg.msg_type == MessageType.TOOL_CALL:
        tool_name = msg.metadata.get("tool_name", "?")
        st.markdown(
            f'<div class="tool-call">🔧 {msg.speaker} → {tool_name}</div>',
            unsafe_allow_html=True,
        )
        return

    if msg.msg_type == MessageType.TOOL_RESULT:
        content = msg.content[:300]
        st.markdown(
            f'<div class="tool-result">{content}</div>',
            unsafe_allow_html=True,
        )
        return

    if msg.msg_type == MessageType.FILE_CHANGE:
        st.markdown(
            f'<div class="file-change">📄 {msg.content}</div>',
            unsafe_allow_html=True,
        )
        return

    if msg.msg_type == MessageType.ROUTE:
        # Inline mailbox routing notice — keep visually quiet.
        st.markdown(
            f'<div class="file-change" style="opacity:0.75">{msg.content}</div>',
            unsafe_allow_html=True,
        )
        return

    if msg.msg_type == MessageType.ERROR:
        st.error(f"❌ {msg.content}")
        return

    # Regular text message
    tag_html = f'<span class="msg-role-tag {cfg["tag_class"]}">{cfg["label"]}</span>'
    header_html = f'<div class="msg-header"><span class="msg-speaker">{cfg["icon"]} {msg.speaker}</span> {tag_html}</div>'

    with st.container(border=True):
        st.markdown(header_html, unsafe_allow_html=True)
        st.markdown(msg.content)


def render_message_header(speaker: str) -> str:
    """Build header HTML for streaming placeholder."""
    cfg = SPEAKER_CONFIG.get(speaker, SPEAKER_CONFIG["System"])
    tag_html = f'<span class="msg-role-tag {cfg["tag_class"]}">{cfg["label"]}</span>'
    return f'<div class="msg-header"><span class="msg-speaker">{cfg["icon"]} {speaker}</span> {tag_html}</div>'
