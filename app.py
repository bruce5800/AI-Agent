"""Streamlit UI for the Multi-Agent Debate System."""

import sys
import os
import re
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from openai import OpenAI
from core.engine import DebateEngine
from core.config import PRO_DEBATERS, CON_DEBATERS, API_KEY, API_BASE_URL, MODEL_NAME
from agents.audience import AUDIENCE_PROFILES
from knowledge.profiles import DEFAULT_TOPIC
from knowledge.generator import generate_profiles

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

    /* ===== Phase-based message background tints ===== */
    .phase-bg-开篇立论 [data-testid="stVerticalBlockBorderWrapper"] {
        background: #fafff8;
    }
    .phase-bg-攻辩质询 [data-testid="stVerticalBlockBorderWrapper"] {
        background: #fffdf5;
    }
    .phase-bg-自由辩论 [data-testid="stVerticalBlockBorderWrapper"] {
        background: #fff8f5;
    }
    .phase-bg-总结陈词 [data-testid="stVerticalBlockBorderWrapper"] {
        background: #f5f8ff;
    }

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

    /* ===== Sidebar debater cards (compact + tooltip) ===== */
    .team-row {
        display: flex;
        gap: 6px;
        margin-bottom: 8px;
    }
    .debater-card {
        flex: 1;
        padding: 6px 10px;
        border-radius: 8px;
        font-size: 0.82em;
        line-height: 1.4;
        cursor: default;
        position: relative;
        transition: box-shadow 0.2s ease;
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
    .debater-card:hover {
        box-shadow: 0 1px 4px rgba(0,0,0,0.12);
    }
    .debater-card-tooltip {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        bottom: 100%;
        left: 0;
        background: #37474f;
        color: white;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.88em;
        line-height: 1.5;
        width: max-content;
        max-width: 200px;
        white-space: normal;
        transition: opacity 0.2s ease;
        pointer-events: none;
        margin-bottom: 6px;
        z-index: 100;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    /* Right-side cards: tooltip aligns to right edge */
    .debater-card:last-child .debater-card-tooltip {
        left: auto;
        right: 0;
    }
    .debater-card:hover .debater-card-tooltip {
        visibility: visible;
        opacity: 1;
    }

    /* ===== Audience chips (compact) ===== */
    .audience-row {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .audience-chip {
        background: #f3e5f5;
        border-radius: 14px;
        padding: 2px 10px;
        font-size: 0.78em;
        color: #6a1b9a;
        cursor: default;
        position: relative;
        transition: all 0.2s ease;
    }
    .audience-chip:hover {
        background: #e1bee7;
        box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    }
    .audience-tooltip {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: #37474f;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85em;
        white-space: nowrap;
        transition: opacity 0.2s ease;
        pointer-events: none;
        margin-bottom: 4px;
        z-index: 100;
    }
    .audience-chip:hover .audience-tooltip {
        visibility: visible;
        opacity: 1;
    }

    /* ===== Fix container max-height (prevent content truncation) ===== */
    [data-testid="stVerticalBlock"] > div {
        max-height: none !important;
        overflow: visible !important;
    }

    /* ===== Mobile responsive ===== */
    @media (max-width: 768px) {
        .block-container { max-width: 100%; padding: 0.5rem 1rem; }
        .team-row { flex-direction: column; }
        .debater-card-tooltip {
            left: 0 !important;
            right: auto !important;
            max-width: 180px;
        }
        .phase-divider { margin: 16px 0 8px 0; }
        .audience-tooltip {
            left: 0 !important;
            transform: none !important;
        }
    }

    /* ===== Topic suggestion chips ===== */
    .topic-chip {
        display: inline-block;
        background: #e3f2fd;
        border: 1px solid #90caf9;
        border-radius: 16px;
        padding: 4px 12px;
        margin: 3px 2px;
        font-size: 0.8em;
        color: #1565c0;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .topic-chip:hover {
        background: #bbdefb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


# --- Helper functions ---
SIDE_CONFIG = {
    "正方": {"icon": "🟢", "tag_class": "tag-pro"},
    "反方": {"icon": "🔴", "tag_class": "tag-con"},
    "主持人": {"icon": "🎙️", "tag_class": "tag-host"},
    "评委": {"icon": "⚖️", "tag_class": "tag-judge"},
    "观众": {"icon": "👥", "tag_class": "tag-audience"},
}

PHASE_ICONS = {
    "开场": "📢", "开篇立论": "📜", "攻辩质询": "⚔️",
    "自由辩论": "🔥", "总结陈词": "📝", "结束": "🏁",
    "评委点评": "⚖️", "观众投票": "🗳️",
}


def render_phase_divider(phase: str):
    """Render a centered phase divider."""
    icon = PHASE_ICONS.get(phase, "▪️")
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
    header_html = f'<div class="msg-header"><span class="msg-speaker">{cfg["icon"]} {msg.speaker}</span> {tag_html}</div>'

    # Use st.container with border for the card
    with st.container(border=True):
        st.markdown(header_html, unsafe_allow_html=True)
        st.markdown(msg.content)


def scroll_to_bottom():
    """Inject JS to scroll the main area to the bottom."""
    st.markdown(
        """<script>
        const main = window.parent.document.querySelector('section.main');
        if (main) main.scrollTop = main.scrollHeight;
        </script>""",
        unsafe_allow_html=True,
    )


def parse_votes(messages) -> tuple:
    """Parse audience vote messages to extract vote counts."""
    votes = {"正方": 0, "反方": 0}
    voter_details = []
    for msg in messages:
        if msg.phase == "观众投票":
            content = msg.content
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


@st.cache_data(ttl=3600, show_spinner=False)
def suggest_topics(user_hint: str) -> list[str]:
    """Call LLM to suggest debate topics based on user's hint."""
    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
    prompt = f"""用户想要一个辩论赛的辩题，ta给出的关键词或方向是："{user_hint}"

请推荐5个适合辩论的辩题。要求：
1. 辩题必须是一个可以有正反两方立场的陈述句
2. 辩题要有争议性，双方都有合理的论据
3. 直接输出JSON数组，不要其他内容

输出格式：["辩题1", "辩题2", "辩题3", "辩题4", "辩题5"]"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        # Extract JSON array from response
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return []


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
        # Custom topic with AI suggestion
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            custom_hint = st.text_input(
                "输入关键词或辩题",
                placeholder="例如：教育、科技、环保...",
                label_visibility="collapsed",
            )
        with col_btn:
            suggest_clicked = st.button("推荐", use_container_width=True)

        # Show suggestions
        if suggest_clicked and custom_hint:
            with st.spinner("AI 正在推荐辩题..."):
                suggestions = suggest_topics(custom_hint)
            if suggestions:
                st.session_state.topic_suggestions = suggestions

        if "topic_suggestions" in st.session_state and st.session_state.topic_suggestions:
            st.caption("💡 点击选择推荐辩题：")
            for i, s in enumerate(st.session_state.topic_suggestions):
                if st.button(s, key=f"suggest_{i}", use_container_width=True):
                    st.session_state.selected_topic = s
                    st.rerun()

        # Determine final topic
        if "selected_topic" in st.session_state and st.session_state.selected_topic:
            topic = st.session_state.selected_topic
            st.success(f"已选择：{topic}")
        else:
            topic = custom_hint
    else:
        topic = topic_choice
        # Clear suggestion state when switching back to presets
        if "selected_topic" in st.session_state:
            st.session_state.selected_topic = ""
        if "topic_suggestions" in st.session_state:
            st.session_state.topic_suggestions = []

    st.markdown("---")
    st.markdown("#### 🟢 正方辩手")
    pro_cards = "".join(
        f"""<div class="debater-card debater-card-pro">
            <div class="debater-card-name">{d['name']}</div>
            <div class="debater-card-tooltip">💡 {d['personality']}<br>🎤 {d['style']}</div>
        </div>"""
        for d in PRO_DEBATERS
    )
    st.markdown(f'<div class="team-row">{pro_cards}</div>', unsafe_allow_html=True)

    st.markdown("#### 🔴 反方辩手")
    con_cards = "".join(
        f"""<div class="debater-card debater-card-con">
            <div class="debater-card-name">{d['name']}</div>
            <div class="debater-card-tooltip">💡 {d['personality']}<br>🎤 {d['style']}</div>
        </div>"""
        for d in CON_DEBATERS
    )
    st.markdown(f'<div class="team-row">{con_cards}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 👥 观众席")
    audience_chips = "".join(
        f"""<span class="audience-chip">{p["name"]}<span class="audience-tooltip">{p["background"]}</span></span>"""
        for p in AUDIENCE_PROFILES
    )
    st.markdown(f'<div class="audience-row">{audience_chips}</div>', unsafe_allow_html=True)


# --- Main area ---
st.markdown("## 辩论赛场")
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

    # For custom topics: generate profiles first
    pro_profiles = None
    con_profiles = None
    if topic != DEFAULT_TOPIC:
        with st.spinner("🧠 正在为辩题生成角色画像和知识图谱..."):
            try:
                pro_profiles, con_profiles = generate_profiles(topic)
                st.success(
                    f"✅ 角色画像生成完成！"
                    f"正方：{', '.join(p.identity.occupation for p in pro_profiles)} | "
                    f"反方：{', '.join(p.identity.occupation for p in con_profiles)}"
                )
            except Exception as e:
                st.warning(f"⚠️ 画像生成失败（{e}），将使用通用辩手配置")

    engine = DebateEngine(topic, pro_profiles, con_profiles)

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
        # Auto-scroll to latest message
        scroll_to_bottom()

    progress_bar.progress(1.0, text="✅ 辩论已结束！")
    st.session_state.debate_running = False
    st.session_state.debate_finished = True

    # Show vote results
    render_vote_results(st.session_state.messages)

    st.balloons()
