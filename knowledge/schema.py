"""Profile schema definitions for debaters and audience."""

from dataclasses import dataclass, field


@dataclass
class Identity:
    """Basic identity of an agent."""
    name: str
    age: int
    occupation: str
    education: str


@dataclass
class Values:
    """Value system that drives decision-making."""
    core_beliefs: list[str] = field(default_factory=list)
    # Weights for different value dimensions (should sum to ~1.0)
    decision_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge with metadata."""
    content: str
    domain: str  # e.g., "经济数据", "法律法规", "社会案例"
    keywords: list[str] = field(default_factory=list)
    # Links knowledge to value dimensions (e.g., ["效率", "创新"])
    # Used by retriever to prioritize knowledge based on agent's value weights
    value_dimensions: list[str] = field(default_factory=list)


@dataclass
class Behavior:
    """Behavioral patterns of an agent."""
    style: str
    emotion_tendency: str
    argument_habits: list[str] = field(default_factory=list)
    catchphrases: list[str] = field(default_factory=list)


@dataclass
class AgentProfile:
    """Complete structured profile for a debate agent."""
    identity: Identity
    role: str  # e.g., "正方一辩（开篇立论）"
    stance: str  # "正方" or "反方"
    values: Values
    knowledge: list[KnowledgeEntry] = field(default_factory=list)
    behavior: Behavior = field(default_factory=lambda: Behavior(
        style="", emotion_tendency="", argument_habits=[], catchphrases=[]
    ))

    @property
    def name(self) -> str:
        return self.identity.name

    def to_prompt_block(self) -> str:
        """Convert the profile into a structured prompt block."""
        lines = []

        # Identity
        lines.append("## 你的身份")
        lines.append(
            f"- 姓名：{self.identity.name}，{self.identity.age}岁"
        )
        lines.append(f"- 职业：{self.identity.occupation}")
        lines.append(f"- 教育背景：{self.identity.education}")

        # Values
        lines.append("\n## 你的价值观")
        for belief in self.values.core_beliefs:
            lines.append(f"- {belief}")

        # Behavior
        lines.append("\n## 你的辩论风格")
        lines.append(f"- 风格：{self.behavior.style}")
        lines.append(f"- 情绪特征：{self.behavior.emotion_tendency}")
        if self.behavior.argument_habits:
            lines.append("- 论证习惯：")
            for habit in self.behavior.argument_habits:
                lines.append(f"  - {habit}")
        if self.behavior.catchphrases:
            lines.append(f"- 口头禅/常用句式：{'、'.join(self.behavior.catchphrases)}")

        return "\n".join(lines)
