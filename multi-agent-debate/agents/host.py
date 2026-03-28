"""Host agent that moderates the debate."""

import json
import re
from agents.base import BaseAgent

HOST_PROMPT = """你是一场辩论赛的主持人。

## 你的职责
1. 宣布辩题和辩论规则
2. 控制辩论流程，引导各环节有序进行
3. 在每个环节开始时做简短的过渡引导
4. 在自由辩论环节，根据场上局势决定下一位发言的辩手
5. 保持中立，不偏向任何一方

## 辩题
{topic}

## 你的风格
专业、从容、有亲和力。语言简洁明了，过渡自然流畅。
直接输出你的发言内容，不要加角色名前缀。
"""

DISPATCH_PROMPT = """你是辩论赛主持人，现在是自由辩论环节，你需要决定下一位发言的辩手。

## 可选辩手
{debater_list}

## 各辩手已发言次数
{speak_counts}

## 最近的辩论内容
{context}

## 调度原则
1. 优先让被对方点名质疑、但尚未回应的辩手发言
2. 避免同一人连续发言，确保双方交替交锋
3. 让发言次数少的辩手有更多机会
4. 如果某个论点需要特定角色（如擅长数据的辩手）来回应，优先选择该辩手

请严格按以下 JSON 格式输出，不要输出其他内容：
{{"selected": "辩手名称", "reason": "一句话说明为什么选这位辩手", "transition": "一句简短的过渡语，引导该辩手发言"}}
"""


class Host(BaseAgent):
    """Moderator agent that controls the debate flow."""

    def __init__(self, topic: str):
        system_prompt = HOST_PROMPT.format(topic=topic)
        super().__init__(name="主持人", system_prompt=system_prompt)

    def opening(self) -> str:
        return self.speak(
            "请做开场白：宣布辩题，简要介绍双方辩手，说明辩论规则和流程。控制在150字以内。"
        )

    def transition(self, phase: str) -> str:
        return self.speak(f"请做过渡引导，当前进入环节：{phase}。控制在50字以内。")

    def closing(self) -> str:
        return self.speak("辩论已结束，请做简短的结束语，感谢双方辩手。控制在80字以内。")

    def dispatch(
        self,
        debater_names: list[str],
        speak_counts: dict[str, int],
        context: str,
    ) -> dict:
        """Decide which debater should speak next.

        Returns:
            dict with keys: selected (str), reason (str), transition (str)
        """
        debater_list = "\n".join(f"- {name}" for name in debater_names)
        counts_str = "\n".join(
            f"- {name}: {count}次" for name, count in speak_counts.items()
        )

        prompt = DISPATCH_PROMPT.format(
            debater_list=debater_list,
            speak_counts=counts_str,
            context=context,
        )

        reply = self.speak(prompt)

        # Parse JSON from LLM response (handle markdown code blocks)
        try:
            # Try to extract JSON from markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', reply, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            # Try direct JSON parse
            return json.loads(reply)
        except (json.JSONDecodeError, AttributeError):
            # Fallback: pick the debater with fewest speaks
            fallback = min(speak_counts, key=speak_counts.get)
            return {
                "selected": fallback,
                "reason": "轮流发言",
                "transition": f"请{fallback}发言。",
            }
