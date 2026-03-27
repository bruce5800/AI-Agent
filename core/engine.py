"""Debate engine that orchestrates the entire debate flow."""

from dataclasses import dataclass, field
from typing import Generator

from agents.debater import Debater
from agents.host import Host
from agents.judge import Judge
from agents.audience import Audience, AUDIENCE_PROFILES
from core.config import (
    PRO_DEBATERS,
    CON_DEBATERS,
    DEBATE_ROUNDS,
    FREE_DEBATE_EXCHANGES,
)


@dataclass
class DebateMessage:
    """A single message in the debate."""
    speaker: str
    content: str
    phase: str
    side: str = ""  # "正方", "反方", "主持人", "评委", "观众"


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
    """

    def __init__(self, topic: str):
        self.topic = topic
        self.state = DebateState(topic=topic)

        # Initialize agents
        self.host = Host(topic)
        self.judge = Judge(topic)

        self.pro_debaters = [
            Debater(p, topic, "正方（支持）") for p in PRO_DEBATERS
        ]
        self.con_debaters = [
            Debater(p, topic, "反方（反对）") for p in CON_DEBATERS
        ]

        self.audience = [Audience(p, topic) for p in AUDIENCE_PROFILES]

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
        statement = self.pro_debaters[0].speak(
            f"请进行开篇立论，阐述正方的核心观点和论证框架。辩题：{self.topic}"
        )
        yield self._add_message(self.pro_debaters[0].name, statement, "开篇立论", "正方")

        # Con first debater
        transition = self.host.transition("请反方一辩进行立论")
        yield self._add_message("主持人", transition, "开篇立论", "主持人")

        context = self._build_context()
        statement = self.con_debaters[0].speak(
            f"对方已经完成立论。以下是目前的辩论内容：\n\n{context}\n\n请进行反方的开篇立论，回应对方观点并阐述你方立场。"
        )
        yield self._add_message(self.con_debaters[0].name, statement, "开篇立论", "反方")

        # === Phase 3: Rebuttal rounds (二辩攻辩) ===
        self.state.current_phase = "攻辩质询"
        transition = self.host.transition("攻辩质询环节——由双方二辩进行交锋")
        yield self._add_message("主持人", transition, "攻辩质询", "主持人")

        for round_num in range(DEBATE_ROUNDS):
            context = self._build_context()

            # Pro second debater
            prompt = f"当前是第{round_num + 1}轮攻辩。以下是目前的辩论内容：\n\n{context}\n\n请针对对方论点进行质询和反驳。"
            reply = self.pro_debaters[1].speak(prompt)
            yield self._add_message(self.pro_debaters[1].name, reply, "攻辩质询", "正方")

            context = self._build_context()

            # Con second debater
            prompt = f"当前是第{round_num + 1}轮攻辩。以下是目前的辩论内容：\n\n{context}\n\n请回应对方的质询并进行反击。"
            reply = self.con_debaters[1].speak(prompt)
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
            transition_line = dispatch.get("transition", f"请{selected_name}发言。")

            # Validate: fallback if Host picks an invalid name
            if selected_name not in debater_map:
                selected_name = min(speak_counts, key=speak_counts.get)
                transition_line = f"请{selected_name}发言。"

            # Avoid same speaker twice in a row
            if selected_name == last_speaker and len(debater_names) > 1:
                # Pick the one with fewest speaks from the other side
                candidates = [
                    n for n in debater_names if n != last_speaker
                ]
                selected_name = min(candidates, key=lambda n: speak_counts[n])
                transition_line = f"请{selected_name}发言。"

            # Host dispatches silently — no visible message in free debate
            dispatch_reason = dispatch.get("reason", "")

            # Selected debater speaks
            debater = debater_map[selected_name]
            side = "正方" if debater in self.pro_debaters else "反方"
            prompt = (
                f"自由辩论环节。你主动站起来发言。\n"
                f"调度提示（观众不可见）：{dispatch_reason}\n\n"
                f"以下是最近的辩论内容：\n\n{context}\n\n"
                f"请回应对方或补充己方论点。简洁有力，控制在100字以内。"
            )
            reply = debater.speak(prompt)
            yield self._add_message(debater.name, reply, "自由辩论", side)

            speak_counts[selected_name] += 1
            last_speaker = selected_name

        # === Phase 5: Closing statements ===
        self.state.current_phase = "总结陈词"
        transition = self.host.transition("总结陈词——请反方三辩先行总结")
        yield self._add_message("主持人", transition, "总结陈词", "主持人")

        context = self._build_context()

        # Con third debater closes first
        closing = self.con_debaters[2].speak(
            f"辩论即将结束。以下是辩论的主要内容：\n\n{context}\n\n请进行反方的总结陈词，概括己方论点，回应对方关键质疑，做出有力收束。"
        )
        yield self._add_message(self.con_debaters[2].name, closing, "总结陈词", "反方")

        transition = self.host.transition("请正方三辩进行总结陈词")
        yield self._add_message("主持人", transition, "总结陈词", "主持人")

        context = self._build_context()
        closing = self.pro_debaters[2].speak(
            f"辩论即将结束。以下是辩论的主要内容：\n\n{context}\n\n请进行正方的总结陈词，概括己方论点，回应对方关键质疑，做出有力收束。"
        )
        yield self._add_message(self.pro_debaters[2].name, closing, "总结陈词", "正方")

        # === Phase 6: Host closing ===
        host_closing = self.host.closing()
        yield self._add_message("主持人", host_closing, "结束", "主持人")

        # === Phase 7: Judge evaluation ===
        self.state.current_phase = "评委点评"
        transcript = self.state.transcript
        evaluation = self.judge.evaluate(transcript)
        yield self._add_message("评委", evaluation, "评委点评", "评委")

        # === Phase 8: Audience voting ===
        self.state.current_phase = "观众投票"
        for member in self.audience:
            vote = member.vote(transcript)
            yield self._add_message(member.name, vote, "观众投票", "观众")

        self.state.current_phase = "辩论结束"
        self.state.is_finished = True
