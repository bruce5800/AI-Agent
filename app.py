"""Streamlit UI for the Multi-Agent Debate System."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from core.engine import DebateEngine
from core.config import PRO_DEBATERS, CON_DEBATERS

# --- Page config ---
st.set_page_config(
    page_title="Multi-Agent Debate",
    page_icon="🎙️",
    layout="wide",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .pro-msg {
        background-color: #e8f5e9;
        border-left: 4px solid #4caf50;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .con-msg {
        background-color: #fce4ec;
        border-left: 4px solid #e53935;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .host-msg {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .judge-msg {
        background-color: #e3f2fd;
        border-left: 4px solid #1976d2;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .audience-msg {
        background-color: #f3e5f5;
        border-left: 4px solid #9c27b0;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .speaker-name {
        font-weight: bold;
        margin-bottom: 4px;
    }
    .phase-badge {
        display: inline-block;
        background-color: #37474f;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("Multi-Agent Debate")
st.sidebar.markdown("多智能体辩论系统")

st.sidebar.markdown("---")
st.sidebar.subheader("辩题设置")

default_topics = [
    "人工智能的发展对人类社会利大于弊",
    "大学教育应该以就业为导向",
    "社交媒体让人们更孤独",
    "远程办公应该成为未来的主流工作方式",
    "自定义辩题...",
]

topic_choice = st.sidebar.selectbox("选择辩题", default_topics)
if topic_choice == "自定义辩题...":
    topic = st.sidebar.text_input("输入辩题", placeholder="例如：科技进步是否会消灭人类的就业机会")
else:
    topic = topic_choice

st.sidebar.markdown("---")
st.sidebar.subheader("辩手阵容")

col1, col2 = st.sidebar.columns(2)
with col1:
    st.markdown("**🟢 正方**")
    for d in PRO_DEBATERS:
        st.caption(f"{d['name']}")
with col2:
    st.markdown("**🔴 反方**")
    for d in CON_DEBATERS:
        st.caption(f"{d['name']}")

# --- Main area ---
st.title("Multi-Agent Debate Arena")

if topic:
    st.markdown(f"**辩题：{topic}**")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "debate_running" not in st.session_state:
    st.session_state.debate_running = False
if "debate_finished" not in st.session_state:
    st.session_state.debate_finished = False


def get_msg_class(side: str) -> str:
    mapping = {
        "正方": "pro-msg",
        "反方": "con-msg",
        "主持人": "host-msg",
        "评委": "judge-msg",
        "观众": "audience-msg",
    }
    return mapping.get(side, "host-msg")


def get_side_icon(side: str) -> str:
    mapping = {
        "正方": "🟢",
        "反方": "🔴",
        "主持人": "🎙️",
        "评委": "⚖️",
        "观众": "👥",
    }
    return mapping.get(side, "💬")


def render_message(msg):
    """Render a debate message with styled container + markdown content."""
    css_class = get_msg_class(msg.side)
    icon = get_side_icon(msg.side)
    side_label = f" [{msg.side}]" if msg.side in ("正方", "反方") else ""

    # Header in HTML (speaker name + phase badge)
    st.markdown(
        f"""<div class="{css_class}">
            <div class="speaker-name">{icon} {msg.speaker}{side_label}
                <span class="phase-badge">{msg.phase}</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    # Content as native Streamlit markdown (supports tables, headers, etc.)
    st.markdown(msg.content)


# Display existing messages
for msg in st.session_state.messages:
    render_message(msg)

# Start debate button
col_start, col_clear = st.columns([1, 1])

with col_start:
    start_clicked = st.button(
        "开始辩论",
        disabled=st.session_state.debate_running or not topic,
        type="primary",
        use_container_width=True,
    )

with col_clear:
    if st.button("清空记录", use_container_width=True):
        st.session_state.messages = []
        st.session_state.debate_running = False
        st.session_state.debate_finished = False
        st.rerun()

if start_clicked and topic:
    st.session_state.messages = []
    st.session_state.debate_running = True
    st.session_state.debate_finished = False

    engine = DebateEngine(topic)

    progress_bar = st.progress(0, text="辩论进行中...")
    total_steps = (
        1  # opening
        + 1 + 2  # opening statements (transition + 2 debaters)
        + 1 + 2 * 3  # rebuttal (transition + rounds * 2)
        + 1 + 6  # free debate (transition + exchanges, host dispatches silently)
        + 3 + 2  # closing (transitions + 2 debaters)
        + 1  # judge
        + 5  # audience
    )
    step = 0

    for msg in engine.run():
        st.session_state.messages.append(msg)
        render_message(msg)
        step += 1
        progress_bar.progress(
            min(step / total_steps, 1.0),
            text=f"辩论进行中... 当前环节：{msg.phase}",
        )

    progress_bar.progress(1.0, text="辩论已结束！")
    st.session_state.debate_running = False
    st.session_state.debate_finished = True
    st.balloons()
