"""Debater agent that argues for a specific stance."""

from agents.base import BaseAgent
from core.config import MAX_WORDS_PER_TURN

DEBATER_PROMPT = """你是{name}，担任{role}。

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

    def __init__(self, profile: dict, topic: str, stance: str):
        system_prompt = DEBATER_PROMPT.format(
            name=profile["name"],
            role=profile["role"],
            personality=profile["personality"],
            style=profile["style"],
            topic=topic,
            stance=stance,
            max_words=MAX_WORDS_PER_TURN,
        )
        super().__init__(name=profile["name"], system_prompt=system_prompt)
        self.stance = stance
