"""Streamlit UI for the Multi-Agent Collaborative Development System."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from core.engine import DevEngine
from core.models import Phase, MessageType, PHASE_LABELS
from core.workspace import list_workspaces
from ui.styles import MAIN_CSS
from ui.components import (
    render_phase_divider,
    render_message,
    render_message_header,
    PHASE_ICONS,
    SPEAKER_CONFIG,
)

# --- Page config ---
st.set_page_config(
    page_title="Multi-Agent Dev",
    page_icon="🤖",
    layout="wide",
)

st.markdown(MAIN_CSS, unsafe_allow_html=True)


# --- Session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "running" not in st.session_state:
    st.session_state.running = False
if "finished" not in st.session_state:
    st.session_state.finished = False
if "engine_generator" not in st.session_state:
    st.session_state.engine_generator = None
if "engine" not in st.session_state:
    st.session_state.engine = None
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None
if "workspace_path" not in st.session_state:
    st.session_state.workspace_path = ""


# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🤖 Multi-Agent Dev")
    st.caption("多智能体协作开发系统")

    st.markdown("---")
    st.markdown("### 🔄 开发流程")
    for phase in Phase:
        if phase == Phase.IDLE:
            continue
        icon = PHASE_ICONS.get(phase, "▪️")
        label = PHASE_LABELS.get(phase, str(phase))
        st.markdown(f"{icon} {label}")

    st.markdown("---")
    st.markdown("### 👥 Agent 团队")
    for name, cfg in SPEAKER_CONFIG.items():
        if name == "System":
            continue
        st.markdown(f"{cfg['icon']} **{cfg['label']}** ({name})")

    st.markdown("---")
    st.markdown("### 📁 历史项目")
    workspaces = list_workspaces()
    if workspaces:
        for ws in workspaces[-5:]:  # Show last 5
            st.caption(f"📂 {ws['name']} ({ws['files']} files)")
    else:
        st.caption("暂无历史项目")


# --- Main area ---
st.markdown("## 开发工作台")

# Display existing messages
last_phase = None
for msg in st.session_state.messages:
    if msg.phase != last_phase:
        render_phase_divider(msg.phase)
        last_phase = msg.phase
    render_message(msg)


def _ui_debug(msg):
    """Mirror engine._debug for UI-side events."""
    import time, sys
    line = f"[{time.strftime('%H:%M:%S')}] [UI] {msg}"
    print(line, file=sys.stderr, flush=True)
    engine = st.session_state.get("engine")
    if engine is not None and getattr(engine, "_workspace", "") and os.path.isdir(engine._workspace):
        try:
            with open(os.path.join(engine._workspace, ".engine.log"), "a") as f:
                f.write(line + "\n")
        except Exception:
            pass


def consume_generator(gen, send_value=None):
    """Drive a DevEngine generator and stream messages to the UI.

    Critical: we iterate ``gen`` directly via ``next(gen)`` rather than
    wrapping it in another generator like ``_chain_first(first, gen)``.

    Why: when the wrapper generator's local reference is dropped (e.g. when
    this function exits via ``RerunException`` from ``st.rerun()``), CPython
    GC calls ``close()`` on the wrapper, which propagates ``GeneratorExit``
    *down* through its ``yield from gen`` — terminating ``gen``. The next
    ``gen.send(...)`` then immediately raises ``StopIteration`` and the
    cleanup branch incorrectly marks the pipeline as finished.

    Iterating ``gen`` directly avoids the wrapper entirely; ``gen`` is still
    held by ``session_state.engine_generator`` across reruns, so it stays
    alive in its paused state.
    """
    _ui_debug(f"consume_generator ENTER send_value={send_value!r} gen={id(gen)}")
    last_phase_local = None
    current_placeholder = None
    current_accumulated = ""
    current_speaker = None
    current_header_html = ""
    msg_count = 0

    def _process(msg):
        """Render a single DevMessage. Returns True if it was an approval gate."""
        nonlocal last_phase_local, current_placeholder, current_accumulated
        nonlocal current_speaker, current_header_html

        if msg.requires_approval:
            _ui_debug(f"  approval msg: pausing, setting pending_approval")
            st.session_state.pending_approval = msg
            st.info(f"⏸️ {msg.content}")
            return True  # caller will st.rerun()

        if msg.is_chunk:
            if msg.speaker != current_speaker or current_placeholder is None:
                if msg.phase != last_phase_local:
                    render_phase_divider(msg.phase)
                    last_phase_local = msg.phase
                current_header_html = render_message_header(msg.speaker)
                current_container = st.container(border=True)
                current_placeholder = current_container.empty()
                current_accumulated = ""
                current_speaker = msg.speaker
            current_accumulated += msg.content
            current_placeholder.markdown(
                current_header_html + "\n\n" + current_accumulated,
                unsafe_allow_html=True,
            )
        else:
            if msg.speaker == current_speaker and current_placeholder is not None:
                if msg.msg_type == MessageType.TEXT:
                    current_placeholder.markdown(
                        current_header_html + "\n\n" + msg.content,
                        unsafe_allow_html=True,
                    )
            else:
                if msg.phase != last_phase_local:
                    render_phase_divider(msg.phase)
                    last_phase_local = msg.phase
                render_message(msg)
            st.session_state.messages.append(msg)
            current_placeholder = None
            current_accumulated = ""
            current_speaker = None
        return False

    try:
        # First message: from gen.send (resume) or next (fresh).
        if send_value is not None:
            _ui_debug(f"  calling gen.send({send_value!r})")
            msg = gen.send(send_value)
        else:
            msg = next(gen)

        while True:
            msg_count += 1
            is_approval = _process(msg)
            if is_approval:
                st.rerun()
                _ui_debug(f"  !!! st.rerun() did NOT raise — fell through")
                return
            msg = next(gen)

    except StopIteration:
        _ui_debug(f"  StopIteration after {msg_count} msgs")

    _ui_debug(f"  try block exited. pending_approval={st.session_state.pending_approval is not None}")

    if not st.session_state.pending_approval:
        _ui_debug(f"  !!! firing FINISHED cleanup")
        engine = st.session_state.get("engine")
        if engine is not None:
            st.session_state.workspace_path = engine.state.workspace_path
        st.session_state.running = False
        st.session_state.finished = True
        st.session_state.engine_generator = None
        st.session_state.engine = None
        st.balloons()


# --- Approval handling ---
if st.session_state.pending_approval:
    _ui_debug(f"render approval branch: speaker={st.session_state.pending_approval.speaker} phase={st.session_state.pending_approval.phase.value}")
    approval_msg = st.session_state.pending_approval
    st.info(f"⏸️ {approval_msg.content}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 通过", type="primary", use_container_width=True):
            _ui_debug(f"button '通过' clicked for phase={approval_msg.phase.value}")
            st.session_state.pending_approval = None
            st.session_state.approval_result = "approved"
            st.rerun()
    with col2:
        if st.button("🔄 重新生成", use_container_width=True):
            _ui_debug(f"button '重新生成' clicked for phase={approval_msg.phase.value}")
            st.session_state.pending_approval = None
            st.session_state.approval_result = "regenerate"
            st.rerun()

# --- Resume after approval ---
elif st.session_state.running and st.session_state.engine_generator and "approval_result" in st.session_state:
    _ui_debug(f"render resume branch: approval_result={st.session_state.approval_result!r}")
    gen = st.session_state.engine_generator
    approval = st.session_state.pop("approval_result", "approved")
    consume_generator(gen, send_value=approval)

# --- Input & Start ---
if not st.session_state.running and not st.session_state.pending_approval:
    requirement = st.text_area(
        "输入你的需求",
        placeholder="例如：用 Python 写一个命令行待办事项管理工具，支持增删改查和持久化存储",
        height=100,
    )

    col_start, col_clear = st.columns([1, 1])
    with col_start:
        start_clicked = st.button(
            "🚀 开始开发",
            disabled=not requirement,
            type="primary",
            use_container_width=True,
        )
    with col_clear:
        if st.button("🗑️ 清空记录", use_container_width=True):
            st.session_state.messages = []
            st.session_state.running = False
            st.session_state.finished = False
            st.session_state.engine_generator = None
            st.session_state.engine = None
            st.session_state.pending_approval = None
            st.session_state.workspace_path = ""
            st.rerun()

    if start_clicked and requirement:
        st.session_state.messages = []
        st.session_state.running = True
        st.session_state.finished = False

        engine = DevEngine(requirement)
        gen = engine.run()
        st.session_state.engine = engine
        st.session_state.engine_generator = gen

        consume_generator(gen)

# Show workspace path when finished
if st.session_state.finished and st.session_state.workspace_path:
    st.success(f"🎉 项目已生成！路径：`{st.session_state.workspace_path}`")

    # Surface the engine debug log so we can diagnose premature termination
    log_path = os.path.join(st.session_state.workspace_path, ".engine.log")
    if os.path.isfile(log_path):
        with open(log_path) as f:
            log_content = f.read()
        with st.expander("🐞 Engine 调度日志（点击展开）", expanded=False):
            st.code(log_content, language="text")
