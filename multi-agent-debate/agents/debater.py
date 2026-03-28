"""Debater agent that argues for a specific stance.

Supports two modes:
  1. Legacy dict profile (backward compatible)
  2. Structured AgentProfile with knowledge graph
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from agents.base import BaseAgent
from core.config import MAX_WORDS_PER_TURN

if TYPE_CHECKING:
    from knowledge.schema import AgentProfile

# System prompt for structured profile mode
DEBATER_PROMPT_V2 = """你是{name}，担任{role}。

{profile_block}

## 辩题
{topic}

## 你的立场
{stance}

## 辩论规则
1. 每次发言控制在{max_words}字以内
2. 必须回应对方最近的论点，不能自说自话
3. 当你的知识储备中有相关信息时，优先引用这些信息来支撑论证，而不是自己编造数据
4. 保持你的角色性格和辩论风格的一致性
5. 禁止人身攻击，专注于论点本身
6. 直接输出你的发言内容，不要加角色名前缀
"""

# System prompt for legacy dict mode (backward compatible)
DEBATER_PROMPT_LEGACY = """你是{name}，担任{role}。

## 你的人设
- 性格特点：{personality}
- 辩论风格：{style}

## 辩题
{topic}

## 你的立场
{stance}

## 辩论规则
1. 每次发言控制在{max_words}字以内
2. 必须回应对方最近的论点，不能自说自话
3. 可以引用数据、案例、学术观点来支撑你的论证
4. 保持你的角色性格和辩论风格的一致性
5. 禁止人身攻击，专注于论点本身
6. 直接输出你的发言内容，不要加角色名前缀
"""


class Debater(BaseAgent):
    """A debater agent with a specific role and stance."""

    def __init__(
        self,
        profile: dict | AgentProfile,
        topic: str,
        stance: str,
    ):
        # Check if it's a structured AgentProfile
        from knowledge.schema import AgentProfile as AP
        if isinstance(profile, AP):
            self._agent_profile = profile
            system_prompt = DEBATER_PROMPT_V2.format(
                name=profile.name,
                role=profile.role,
                profile_block=profile.to_prompt_block(),
                topic=topic,
                stance=stance,
                max_words=MAX_WORDS_PER_TURN,
            )
            name = profile.name
        else:
            # Legacy dict mode
            self._agent_profile = None
            system_prompt = DEBATER_PROMPT_LEGACY.format(
                name=profile["name"],
                role=profile["role"],
                personality=profile["personality"],
                style=profile["style"],
                topic=topic,
                stance=stance,
                max_words=MAX_WORDS_PER_TURN,
            )
            name = profile["name"]

        super().__init__(name=name, system_prompt=system_prompt)
        self.stance = stance

    @property
    def has_knowledge(self) -> bool:
        """Check if this debater has a knowledge graph."""
        return (
            self._agent_profile is not None
            and len(self._agent_profile.knowledge) > 0
        )

    @property
    def agent_profile(self) -> AgentProfile | None:
        return self._agent_profile
