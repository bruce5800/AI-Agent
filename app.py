"""Streamlit UI for the Multi-Agent Debate System."""

import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from core.engine import DebateEngine
from core.config import PRO_DEBATERS, CON_DEBATERS
from agents.audience import AUDIENCE_PROFILES

# --- Page config ---
st.set_page_config(
    page_title="Multi-Agent Debate Arena",
    page_icon="🎙️",
    layout="wide",
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* ===== Global ===== */
    .block-container { max-width: 900px; }

    /* ===== Phase divider ===== */
    .phase-divider {
        display: flex;
        align-items: center;
        margin: 28px 0 16px 0;
        gap: 12px;
    }
    .phase-divider::before, .phase-divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(to right, transparent, #bdbdbd, transparent);
    }
    .phase-divider-text {
        font-size: 0.9em;
        font-weight: 600;
        color: #546e7a;
        white-space: nowrap;
        letter-spacing: 2px;
    }

    /* ===== Message card header ===== */
    .msg-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 2px;
    }
    .msg-speaker {
        font-weight: 700;
        font-size: 0.95em;
    }
    .msg-side-tag {
        font-size: 0.75em;
        padding: 1px 8px;
        border-radius: 10px;
        font-weight: 500;
    }
    .tag-pro { background: #c8e6c9; color: #2e7d32; }
    .tag-con { background: #ffcdd2; color: #c62828; }
    .tag-host { background: #ffe0b2; color: #e65100; }
    .tag-judge { background: #bbdefb; color: #1565c0; }
    .tag-audience { background: #e1bee7; color: #7b1fa2; }

    /* ===== Vote result card ===== */
    .vote-summary {
        background: linear-gradient(135deg, #e8f5e9 0%, #fce4ec 100%);
        border-radius: 12px;
        padding: 20px 24px;
        margin: 16px 0;
        text-align: center;
    }
    .vote-title {
        font-size: 1.2em;
        font-weight: 700;
        margin-bottom: 12px;
        color: #37474f;
    }

    /* ===== Sidebar debater cards ===== */
    .debater-card {
        padding: 8px 10px;
        border-radius: 8px;
        margin-bottom: 6px;
        font-size: 0.82em;
        line-height: 1.4;
    }
    .debater-card-pro {
        background: #e8f5e9;
        border-left: 3px solid #4caf50;
    }
    .debater-card-con {
        background: #fce4ec;
        border-left: 3px solid #e53935;
    }
    .debater-card-name {
        font-weight: 700;
        font-size: 0.9em;
    }
    .debater-card-detail {
        color: #616161;
        margin-top: 2px;
    }

    /* ===== Audience card ===== */
    .audience-card {
        display: inline-block;
        background: #f3e5f5;
        border-radius: 16px;
        padding: 3px 12px;
        margin: 2px 4px;
        font-size: 0.8em;
        color: #6a1b9a;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper functions ---
SIDE_CONFIG = {
    "正方": {"icon": "🟢", "tag_class": "tag-pro", "border_color": "#4caf50", "bg_color": "#f1f8e9"},
    "反方": {"icon": "🔴", "tag_class": "tag-con", "border_color": "#e53935", "bg_color": "#fce4ec"},
    "主持人": {"icon": "🎙️", "tag_class": "tag-host", "border_color": "#ff9800", "bg_color": "#fff8e1"},
    "评委": {"icon": "⚖️", "tag_class": "tag-judge", "border_color": "#1976d2", "bg_color": "#e3f2fd"},
    "观众": {"icon": "👥", "tag_class": "tag-audience", "border_color": "#9c27b0", "bg_color": "#f3e5f5"},
}


def render_phase_divider(phase: str):
    """Render a centered phase divider."""
    phase_icons = {
        "开场": "📢",
        "开篇立论": "📜",
        "攻辩质询": "⚔️",
        "自由辩论": "🔥",
        "总结陈词": "📝",
        "结束": "🏁",
        "评委点评": "⚖️",
        "观众投票": "🗳️",
    }
    icon = phase_icons.get(phase, "▪️")
    st.markdown(
        f'<div class="phase-divider"><span class="phase-divider-text">{icon} {phase}</span></div>',
        unsafe_allow_html=True,
    )


def render_message(msg):
    """Render a debate message using Streamlit native container with colored border."""
    cfg = SIDE_CONFIG.get(msg.side, SIDE_CONFIG["主持人"])

    # Build header HTML
    side_label = msg.side if msg.side in ("正方", "反方") else ""
    tag_html = (
        f'<span class="msg-side-tag {cfg["tag_class"]}">{side_label}</span>'
        if side_label
        else ""
    )
    header_html = f"""<div class="msg-header">
        <span class="msg-speaker">{cfg["icon"]} {msg.speaker}</span>
        {tag_html}
    </div>"""

    # Use st.container with border for the card
    with st.container(border=True):
        st.markdown(header_html, unsafe_allow_html=True)
        st.markdown(msg.content)


def parse_votes(messages) -> dict:
    """Parse audience vote messages to extract vote counts."""
    votes = {"正方": 0, "反方": 0}
    voter_details = []
    for msg in messages:
        if msg.phase == "观众投票":
            content = msg.content
            # Try to match vote pattern
            if "正方" in content and ("我的投票" in content or "投票" in content):
                if "反方" not in content.split("我的投票")[-1] if "我的投票" in content else True:
                    pass  # need more careful parsing
            # Simple heuristic: find the line with "我的投票"
            for line in content.split("\n"):
                if "投票" in line and ("正方" in line or "反方" in line):
                    if "正方" in line and "反方" not in line:
                        votes["正方"] += 1
                        voter_details.append((msg.speaker, "正方"))
                        break
                    elif "反方" in line and "正方" not in line:
                        votes["反方"] += 1
                        voter_details.append((msg.speaker, "反方"))
                        break
                    elif "正方" in line and "反方" in line:
                        # Both mentioned — check which comes after "投票："
                        match = re.search(r"投票[：:]\s*(正方|反方)", line)
                        if match:
                            side = match.group(1)
                            votes[side] += 1
                            voter_details.append((msg.speaker, side))
                            break
    return votes, voter_details


def render_vote_results(messages):
    """Render vote statistics with a bar chart."""
    votes, voter_details = parse_votes(messages)
    total = votes["正方"] + votes["反方"]
    if total == 0:
        return

    st.markdown("---")
    st.markdown(
        '<div class="vote-summary"><div class="vote-title">🗳️ 观众投票统计</div></div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        st.metric("🟢 正方", f"{votes['正方']} 票")
    with col3:
        st.metric("🔴 反方", f"{votes['反方']} 票")

    with col2:
        # Horizontal bar using st.progress
        pro_pct = votes["正方"] / total if total > 0 else 0
        con_pct = votes["反方"] / total if total > 0 else 0

        st.caption("正方得票率")
        st.progress(pro_pct, text=f"{pro_pct:.0%}")
        st.caption("反方得票率")
        st.progress(con_pct, text=f"{con_pct:.0%}")

    # Winner announcement
    if votes["正方"] > votes["反方"]:
        st.success(f"🏆 观众投票结果：**正方** 以 {votes['正方']}:{votes['反方']} 获胜！")
    elif votes["反方"] > votes["正方"]:
        st.error(f"🏆 观众投票结果：**反方** 以 {votes['反方']}:{votes['正方']} 获胜！")
    else:
        st.info(f"🤝 观众投票结果：**平局** {votes['正方']}:{votes['反方']}")

    # Voter breakdown
    if voter_details:
        with st.expander("查看每位观众的投票"):
            for name, side in voter_details:
                icon = "🟢" if side == "正方" else "🔴"
                st.markdown(f"- {icon} **{name}** → {side}")


# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🎙️ Multi-Agent Debate")
    st.caption("多智能体辩论系统")

    st.markdown("---")
    st.markdown("### 📋 辩题设置")

    default_topics = [
        "人工智能的发展对人类社会利大于弊",
        "大学教育应该以就业为导向",
        "社交媒体让人们更孤独",
        "远程办公应该成为未来的主流工作方式",
        "自定义辩题...",
    ]

    topic_choice = st.selectbox("选择辩题", default_topics, label_visibility="collapsed")
    if topic_choice == "自定义辩题...":
        topic = st.text_input("输入辩题", placeholder="例如：科技进步是否会消灭人类的就业机会")
    else:
        topic = topic_choice

    st.markdown("---")
    st.markdown("### 🟢 正方辩手")
    for d in PRO_DEBATERS:
        st.markdown(
            f"""<div class="debater-card debater-card-pro">
                <div class="debater-card-name">{d['name']}</div>
                <div class="debater-card-detail">💡 {d['personality']}</div>
                <div class="debater-card-detail">🎤 {d['style']}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("### 🔴 反方辩手")
    for d in CON_DEBATERS:
        st.markdown(
            f"""<div class="debater-card debater-card-con">
                <div class="debater-card-name">{d['name']}</div>
                <div class="debater-card-detail">💡 {d['personality']}</div>
                <div class="debater-card-detail">🎤 {d['style']}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 👥 观众席")
    audience_html = "".join(
        f'<span class="audience-card">{p["name"]} · {p["background"]}</span>'
        for p in AUDIENCE_PROFILES
    )
    st.markdown(audience_html, unsafe_allow_html=True)


# --- Main area ---
st.markdown(f"## 辩论赛场")
if topic:
    st.markdown(f"> **辩题：{topic}**")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "debate_running" not in st.session_state:
    st.session_state.debate_running = False
if "debate_finished" not in st.session_state:
    st.session_state.debate_finished = False

# --- Display existing messages with phase dividers ---
last_phase = None
for msg in st.session_state.messages:
    if msg.phase != last_phase:
        render_phase_divider(msg.phase)
        last_phase = msg.phase
    render_message(msg)

# Show vote results if debate is finished
if st.session_state.debate_finished:
    render_vote_results(st.session_state.messages)

# --- Controls ---
st.markdown("")  # spacing
col_start, col_clear = st.columns([1, 1])

with col_start:
    start_clicked = st.button(
        "⚡ 开始辩论",
        disabled=st.session_state.debate_running or not topic,
        type="primary",
        use_container_width=True,
    )

with col_clear:
    if st.button("🗑️ 清空记录", use_container_width=True):
        st.session_state.messages = []
        st.session_state.debate_running = False
        st.session_state.debate_finished = False
        st.rerun()

# --- Run debate ---
if start_clicked and topic:
    st.session_state.messages = []
    st.session_state.debate_running = True
    st.session_state.debate_finished = False

    engine = DebateEngine(topic)

    progress_bar = st.progress(0, text="辩论准备中...")
    total_steps = (
        1  # opening
        + 1 + 2  # opening statements
        + 1 + 2 * 3  # rebuttal
        + 1 + 6  # free debate
        + 3 + 2  # closing
        + 1  # judge
        + 5  # audience
    )
    step = 0
    last_phase = None

    for msg in engine.run():
        st.session_state.messages.append(msg)
        # Phase divider
        if msg.phase != last_phase:
            render_phase_divider(msg.phase)
            last_phase = msg.phase
        render_message(msg)
        step += 1
        progress_bar.progress(
            min(step / total_steps, 1.0),
            text=f"辩论进行中... {msg.phase}",
        )

    progress_bar.progress(1.0, text="✅ 辩论已结束！")
    st.session_state.debate_running = False
    st.session_state.debate_finished = True

    # Show vote results
    render_vote_results(st.session_state.messages)

    st.balloons()
