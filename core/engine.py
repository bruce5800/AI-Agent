"""Debate engine that orchestrates the entire debate flow."""

from dataclasses import dataclass, field
from typing import Generator

from agents.debater import Debater
from agents.host import Host
from agents.judge import Judge
from agents.audience import Audience, AudienceVoteResult, DEFAULT_AUDIENCE_PROFILES, assign_audience_weights
from core.config import (
    PRO_DEBATERS,
    CON_DEBATERS,
    DEBATE_ROUNDS,
    FREE_DEBATE_EXCHANGES,
)
from knowledge.retriever import retrieve, format_knowledge_for_prompt
from knowledge.profiles import (
    DEFAULT_TOPIC,
    DEFAULT_PRO_PROFILES,
    DEFAULT_CON_PROFILES,
)
from knowledge.generator import generate_profiles


@dataclass
class DebateMessage:
    """A single message in the debate."""
    speaker: str
    content: str
    phase: str
    side: str = ""  # "正方", "反方", "主持人", "评委", "观众"
    vote_result: AudienceVoteResult | None = None  # structured vote data
    is_chunk: bool = False  # True = streaming delta token, False = complete message


@dataclass
class DebateState:
    """Tracks the full state of a debate."""
    topic: str
    messages: list[DebateMessage] = field(default_factory=list)
    current_phase: str = "未开始"
    is_finished: bool = False

    @property
    def transcript(self) -> str:
        """Generate a formatted transcript of the debate."""
        lines = []
        for msg in self.messages:
            if msg.side in ("正方", "反方"):
                lines.append(f"【{msg.side} - {msg.speaker}】\n{msg.content}\n")
            else:
                lines.append(f"【{msg.speaker}】\n{msg.content}\n")
        return "\n".join(lines)


class DebateEngine:
    """Orchestrates the full debate process.

    Uses a generator pattern so the UI can stream messages in real time.
    Supports knowledge graph profiles for richer, more grounded arguments.
    """

    def __init__(
        self,
        topic: str,
        pro_profiles: list | None = None,
        con_profiles: list | None = None,
    ):
        self.topic = topic
        self.state = DebateState(topic=topic)

        # Initialize agents
        self.host = Host(topic)
        self.judge = Judge(topic)

        # Use provided profiles, or fall back to defaults / generation
        if pro_profiles and con_profiles:
            # Profiles provided externally (pre-generated or default)
            self.pro_debaters = [
                Debater(p, topic, "正方（支持）") for p in pro_profiles
            ]
            self.con_debaters = [
                Debater(p, topic, "反方（反对）") for p in con_profiles
            ]
        elif topic == DEFAULT_TOPIC:
            self.pro_debaters = [
                Debater(p, topic, "正方（支持）") for p in DEFAULT_PRO_PROFILES
            ]
            self.con_debaters = [
                Debater(p, topic, "反方（反对）") for p in DEFAULT_CON_PROFILES
            ]
        else:
            # Generate profiles on the fly for custom topics
            pro_gen, con_gen = generate_profiles(topic)
            self.pro_debaters = [
                Debater(p, topic, "正方（支持）") for p in pro_gen
            ]
            self.con_debaters = [
                Debater(p, topic, "反方（反对）") for p in con_gen
            ]

        # Extract value dimensions from debater profiles
        self.value_dims = self._extract_value_dims()

        # Create audience with value-weighted profiles
        audience_profiles = assign_audience_weights(self.value_dims)
        self.audience = [Audience(p, topic, self.value_dims) for p in audience_profiles]
        self.vote_results: list[AudienceVoteResult] = []

    def _extract_value_dims(self) -> list[str]:
        """Extract value dimensions from debater profiles."""
        dims: list[str] = []
        all_debaters = self.pro_debaters + self.con_debaters
        for d in all_debaters:
            if d.has_knowledge and hasattr(d.agent_profile, 'get_value_dims'):
                for dim in d.agent_profile.get_value_dims():
                    if dim not in dims:
                        dims.append(dim)
        # Fallback: if no structured profiles, use common defaults
        if not dims:
            dims = ["效率", "公平", "安全"]
        return dims[:3]  # Keep top 3

    def _add_message(self, speaker: str, content: str, phase: str, side: str = "") -> DebateMessage:
        msg = DebateMessage(speaker=speaker, content=content, phase=phase, side=side)
        self.state.messages.append(msg)
        return msg

    def _build_context(self) -> str:
        """Build the recent debate context for debaters to reference."""
        recent = self.state.messages[-10:]  # Last 10 messages for context
        lines = []
        for msg in recent:
            if msg.side in ("正方", "反方"):
                lines.append(f"{msg.side}{msg.speaker}：{msg.content}")
            elif msg.side != "主持人":
                lines.append(f"{msg.speaker}：{msg.content}")
        return "\n\n".join(lines)

    def _inject_knowledge(self, debater: Debater, context: str) -> str:
        """Retrieve relevant knowledge and format as injectable prompt block."""
        if not debater.has_knowledge:
            return ""
        entries = retrieve(debater.agent_profile, context, top_k=4)
        return format_knowledge_for_prompt(entries)

    def _debater_speak(self, debater: Debater, prompt: str, context: str) -> str:
        """Have a debater speak, with knowledge injection if available."""
        knowledge_block = self._inject_knowledge(debater, context)
        if knowledge_block:
            full_prompt = f"{prompt}\n\n{knowledge_block}"
        else:
            full_prompt = prompt
        return debater.speak(full_prompt)

    def _build_debater_prompt(self, debater: Debater, prompt: str, context: str) -> str:
        """Build the full prompt for a debater (with knowledge injection)."""
        knowledge_block = self._inject_knowledge(debater, context)
        if knowledge_block:
            return f"{prompt}\n\n{knowledge_block}"
        return prompt

    def _format_vote_display(self, result: AudienceVoteResult) -> str:
        """Format a structured vote result into readable text."""
        lines = []
        lines.append(f"**印象最深：** {result.comment}")
        lines.append("")
        lines.append("| 价值维度 | 我的权重 | 正方得分 | 反方得分 |")
        lines.append("|:------:|:------:|:------:|:------:|")
        for ds in result.dimension_scores:
            w = result.weights.get(ds.dimension, 0)
            lines.append(f"| {ds.dimension} | {w:.0%} | {ds.pro_score} | {ds.con_score} |")
        lines.append("")
        lines.append(f"**加权得分：** 正方 **{result.weighted_pro:.2f}** vs 反方 **{result.weighted_con:.2f}**")
        lines.append("")
        lines.append(f"**我的投票：{result.vote}**")
        lines.append(f"**理由：** {result.reason}")
        return "\n".join(lines)

    def run(self) -> Generator[DebateMessage, None, None]:
        """Run the full debate, yielding each message as it's generated."""

        # === Phase 1: Opening ===
        self.state.current_phase = "开场"
        opening = self.host.opening()
        yield self._add_message("主持人", opening, "开场", "主持人")

        # === Phase 2: Opening statements ===
        self.state.current_phase = "开篇立论"
        transition = self.host.transition("开篇立论——请正方一辩先行立论")
        yield self._add_message("主持人", transition, "开篇立论", "主持人")

        # Pro first debater
        base_prompt = f"请进行开篇立论，阐述正方的核心观点和论证框架。辩题：{self.topic}"
        statement = self._debater_speak(
            self.pro_debaters[0], base_prompt, self.topic,
        )
        yield self._add_message(self.pro_debaters[0].name, statement, "开篇立论", "正方")

        # Con first debater
        transition = self.host.transition("请反方一辩进行立论")
        yield self._add_message("主持人", transition, "开篇立论", "主持人")

        context = self._build_context()
        base_prompt = f"对方已经完成立论。以下是目前的辩论内容：\n\n{context}\n\n请进行反方的开篇立论，回应对方观点并阐述你方立场。"
        statement = self._debater_speak(
            self.con_debaters[0], base_prompt, context,
        )
        yield self._add_message(self.con_debaters[0].name, statement, "开篇立论", "反方")

        # === Phase 3: Rebuttal rounds (二辩攻辩) ===
        self.state.current_phase = "攻辩质询"
        transition = self.host.transition("攻辩质询环节——由双方二辩进行交锋")
        yield self._add_message("主持人", transition, "攻辩质询", "主持人")

        for round_num in range(DEBATE_ROUNDS):
            context = self._build_context()

            # Pro second debater
            base_prompt = f"当前是第{round_num + 1}轮攻辩。以下是目前的辩论内容：\n\n{context}\n\n请针对对方论点进行质询和反驳。"
            reply = self._debater_speak(self.pro_debaters[1], base_prompt, context)
            yield self._add_message(self.pro_debaters[1].name, reply, "攻辩质询", "正方")

            context = self._build_context()

            # Con second debater
            base_prompt = f"当前是第{round_num + 1}轮攻辩。以下是目前的辩论内容：\n\n{context}\n\n请回应对方的质询并进行反击。"
            reply = self._debater_speak(self.con_debaters[1], base_prompt, context)
            yield self._add_message(self.con_debaters[1].name, reply, "攻辩质询", "反方")

        # === Phase 4: Free debate (Host-dispatched) ===
        self.state.current_phase = "自由辩论"
        transition = self.host.transition("自由辩论环节——双方可自由发言交锋")
        yield self._add_message("主持人", transition, "自由辩论", "主持人")

        # Build debater lookup and speak counter
        all_debaters = self.pro_debaters + self.con_debaters
        debater_map = {d.name: d for d in all_debaters}
        debater_names = [d.name for d in all_debaters]
        speak_counts = {d.name: 0 for d in all_debaters}
        last_speaker = None

        for i in range(FREE_DEBATE_EXCHANGES):
            context = self._build_context()

            # Host decides who speaks next
            dispatch = self.host.dispatch(debater_names, speak_counts, context)
            selected_name = dispatch["selected"]

            # Validate: fallback if Host picks an invalid name
            if selected_name not in debater_map:
                selected_name = min(speak_counts, key=speak_counts.get)

            # Avoid same speaker twice in a row
            if selected_name == last_speaker and len(debater_names) > 1:
                candidates = [
                    n for n in debater_names if n != last_speaker
                ]
                selected_name = min(candidates, key=lambda n: speak_counts[n])

            # Host dispatches silently — no visible message in free debate
            dispatch_reason = dispatch.get("reason", "")

            # Selected debater speaks
            debater = debater_map[selected_name]
            side = "正方" if debater in self.pro_debaters else "反方"
            base_prompt = (
                f"自由辩论环节。你主动站起来发言。\n"
                f"调度提示（观众不可见）：{dispatch_reason}\n\n"
                f"以下是最近的辩论内容：\n\n{context}\n\n"
                f"请回应对方或补充己方论点。简洁有力，控制在100字以内。"
            )
            reply = self._debater_speak(debater, base_prompt, context)
            yield self._add_message(debater.name, reply, "自由辩论", side)

            speak_counts[selected_name] += 1
            last_speaker = selected_name

        # === Phase 5: Closing statements ===
        self.state.current_phase = "总结陈词"
        transition = self.host.transition("总结陈词——请反方三辩先行总结")
        yield self._add_message("主持人", transition, "总结陈词", "主持人")

        context = self._build_context()

        # Con third debater closes first
        base_prompt = f"辩论即将结束。以下是辩论的主要内容：\n\n{context}\n\n请进行反方的总结陈词，概括己方论点，回应对方关键质疑，做出有力收束。"
        closing = self._debater_speak(self.con_debaters[2], base_prompt, context)
        yield self._add_message(self.con_debaters[2].name, closing, "总结陈词", "反方")

        transition = self.host.transition("请正方三辩进行总结陈词")
        yield self._add_message("主持人", transition, "总结陈词", "主持人")

        context = self._build_context()
        base_prompt = f"辩论即将结束。以下是辩论的主要内容：\n\n{context}\n\n请进行正方的总结陈词，概括己方论点，回应对方关键质疑，做出有力收束。"
        closing = self._debater_speak(self.pro_debaters[2], base_prompt, context)
        yield self._add_message(self.pro_debaters[2].name, closing, "总结陈词", "正方")

        # === Phase 6: Host closing ===
        host_closing = self.host.closing()
        yield self._add_message("主持人", host_closing, "结束", "主持人")

        # === Phase 7: Judge evaluation ===
        self.state.current_phase = "评委点评"
        transcript = self.state.transcript
        evaluation = self.judge.evaluate(transcript)
        yield self._add_message("评委", evaluation, "评委点评", "评委")

        # === Phase 8: Audience voting (value-weighted) ===
        self.state.current_phase = "观众投票"
        for member in self.audience:
            raw_text, vote_result = member.vote(transcript)
            if vote_result:
                self.vote_results.append(vote_result)
                # Build human-readable display text
                display = self._format_vote_display(vote_result)
            else:
                display = raw_text  # Fallback: show raw LLM output
            msg = self._add_message(member.name, display, "观众投票", "观众")
            msg.vote_result = vote_result
            yield msg

        self.state.current_phase = "辩论结束"
        self.state.is_finished = True

    # ------------------------------------------------------------------
    # Streaming version — yields chunk messages for token-by-token render
    # ------------------------------------------------------------------

    def _stream_agent(
        self, agent, prompt: str, speaker: str, phase: str, side: str,
    ) -> Generator[DebateMessage, None, None]:
        """Stream an agent's response token by token, then yield the final message."""
        full_text = ""
        for delta in agent.speak_stream(prompt):
            full_text += delta
            yield DebateMessage(
                speaker=speaker, content=delta, phase=phase, side=side, is_chunk=True,
            )
        # Yield final complete message and add to state
        msg = self._add_message(speaker, full_text, phase, side)
        yield msg

    def _stream_debater(
        self, debater: Debater, prompt: str, context: str, phase: str, side: str,
    ) -> Generator[DebateMessage, None, None]:
        """Stream a debater's response with knowledge injection."""
        full_prompt = self._build_debater_prompt(debater, prompt, context)
        yield from self._stream_agent(debater, full_prompt, debater.name, phase, side)

    def run_stream(self) -> Generator[DebateMessage, None, None]:
        """Run the full debate with token-level streaming.

        Yields DebateMessage with is_chunk=True for streaming deltas,
        and is_chunk=False for complete messages (used for state tracking).
        """

        # === Phase 1: Opening ===
        self.state.current_phase = "开场"
        yield from self._stream_agent(
            self.host,
            "请做开场白：宣布辩题，简要介绍双方辩手，说明辩论规则和流程。控制在150字以内。",
            "主持人", "开场", "主持人",
        )

        # === Phase 2: Opening statements ===
        self.state.current_phase = "开篇立论"
        yield from self._stream_agent(
            self.host, "请做过渡引导，当前进入环节：开篇立论——请正方一辩先行立论。控制在50字以内。",
            "主持人", "开篇立论", "主持人",
        )

        base_prompt = f"请进行开篇立论，阐述正方的核心观点和论证框架。辩题：{self.topic}"
        yield from self._stream_debater(
            self.pro_debaters[0], base_prompt, self.topic, "开篇立论", "正方",
        )

        yield from self._stream_agent(
            self.host, "请做过渡引导，当前进入环节：请反方一辩进行立论。控制在50字以内。",
            "主持人", "开篇立论", "主持人",
        )

        context = self._build_context()
        base_prompt = f"对方已经完成立论。以下是目前的辩论内容：\n\n{context}\n\n请进行反方的开篇立论，回应对方观点并阐述你方立场。"
        yield from self._stream_debater(
            self.con_debaters[0], base_prompt, context, "开篇立论", "反方",
        )

        # === Phase 3: Rebuttal rounds ===
        self.state.current_phase = "攻辩质询"
        yield from self._stream_agent(
            self.host, "请做过渡引导，当前进入环节：攻辩质询环节——由双方二辩进行交锋。控制在50字以内。",
            "主持人", "攻辩质询", "主持人",
        )

        for round_num in range(DEBATE_ROUNDS):
            context = self._build_context()
            base_prompt = f"当前是第{round_num + 1}轮攻辩。以下是目前的辩论内容：\n\n{context}\n\n请针对对方论点进行质询和反驳。"
            yield from self._stream_debater(
                self.pro_debaters[1], base_prompt, context, "攻辩质询", "正方",
            )

            context = self._build_context()
            base_prompt = f"当前是第{round_num + 1}轮攻辩。以下是目前的辩论内容：\n\n{context}\n\n请回应对方的质询并进行反击。"
            yield from self._stream_debater(
                self.con_debaters[1], base_prompt, context, "攻辩质询", "反方",
            )

        # === Phase 4: Free debate ===
        self.state.current_phase = "自由辩论"
        yield from self._stream_agent(
            self.host, "请做过渡引导，当前进入环节：自由辩论环节——双方可自由发言交锋。控制在50字以内。",
            "主持人", "自由辩论", "主持人",
        )

        all_debaters = self.pro_debaters + self.con_debaters
        debater_map = {d.name: d for d in all_debaters}
        debater_names = [d.name for d in all_debaters]
        speak_counts = {d.name: 0 for d in all_debaters}
        last_speaker = None

        for i in range(FREE_DEBATE_EXCHANGES):
            context = self._build_context()

            # Host dispatch (not streamed — internal JSON)
            dispatch = self.host.dispatch(debater_names, speak_counts, context)
            selected_name = dispatch["selected"]

            if selected_name not in debater_map:
                selected_name = min(speak_counts, key=speak_counts.get)
            if selected_name == last_speaker and len(debater_names) > 1:
                candidates = [n for n in debater_names if n != last_speaker]
                selected_name = min(candidates, key=lambda n: speak_counts[n])

            dispatch_reason = dispatch.get("reason", "")
            debater = debater_map[selected_name]
            side = "正方" if debater in self.pro_debaters else "反方"
            base_prompt = (
                f"自由辩论环节。你主动站起来发言。\n"
                f"调度提示（观众不可见）：{dispatch_reason}\n\n"
                f"以下是最近的辩论内容：\n\n{context}\n\n"
                f"请回应对方或补充己方论点。简洁有力，控制在100字以内。"
            )
            yield from self._stream_debater(debater, base_prompt, context, "自由辩论", side)

            speak_counts[selected_name] += 1
            last_speaker = selected_name

        # === Phase 5: Closing statements ===
        self.state.current_phase = "总结陈词"
        yield from self._stream_agent(
            self.host, "请做过渡引导，当前进入环节：总结陈词——请反方三辩先行总结。控制在50字以内。",
            "主持人", "总结陈词", "主持人",
        )

        context = self._build_context()
        base_prompt = f"辩论即将结束。以下是辩论的主要内容：\n\n{context}\n\n请进行反方的总结陈词，概括己方论点，回应对方关键质疑，做出有力收束。"
        yield from self._stream_debater(
            self.con_debaters[2], base_prompt, context, "总结陈词", "反方",
        )

        yield from self._stream_agent(
            self.host, "请做过渡引导，当前进入环节：请正方三辩进行总结陈词。控制在50字以内。",
            "主持人", "总结陈词", "主持人",
        )

        context = self._build_context()
        base_prompt = f"辩论即将结束。以下是辩论的主要内容：\n\n{context}\n\n请进行正方的总结陈词，概括己方论点，回应对方关键质疑，做出有力收束。"
        yield from self._stream_debater(
            self.pro_debaters[2], base_prompt, context, "总结陈词", "正方",
        )

        # === Phase 6: Host closing ===
        yield from self._stream_agent(
            self.host, "辩论已结束，请做简短的结束语，感谢双方辩手。控制在80字以内。",
            "主持人", "结束", "主持人",
        )

        # === Phase 7: Judge evaluation (streamed) ===
        self.state.current_phase = "评委点评"
        transcript = self.state.transcript
        judge_prompt = f"""以下是完整的辩论记录：

{transcript}

请根据评判标准对这场辩论进行点评和打分。请按以下格式输出：

### 正方点评
（亮点与不足）

### 反方点评
（亮点与不足）

### 评分
| 维度 | 正方得分 | 反方得分 |
|------|---------|---------|
| 论点质量 | /30 | /30 |
| 逻辑严密性 | /25 | /25 |
| 回应能力 | /25 | /25 |
| 表达与风度 | /20 | /20 |
| **总分** | **/100** | **/100** |

### 最终判定
（宣布获胜方及理由）"""
        yield from self._stream_agent(self.judge, judge_prompt, "评委", "评委点评", "评委")

        # === Phase 8: Audience voting (not streamed — needs JSON parsing) ===
        self.state.current_phase = "观众投票"
        for member in self.audience:
            raw_text, vote_result = member.vote(transcript)
            if vote_result:
                self.vote_results.append(vote_result)
                display = self._format_vote_display(vote_result)
            else:
                display = raw_text
            msg = self._add_message(member.name, display, "观众投票", "观众")
            msg.vote_result = vote_result
            yield msg

        self.state.current_phase = "辩论结束"
        self.state.is_finished = True
