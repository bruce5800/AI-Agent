"""Audience agents that react to the debate and vote."""

from agents.base import BaseAgent

AUDIENCE_PROMPT = """你是辩论赛的一名观众，名叫{name}。

## 你的背景
{background}

## 辩题
{topic}

## 你的任务
观看辩论后，根据你的背景和价值观：
1. 简短评论你印象最深的论点（1-2句话）
2. 投出你的一票（正方或反方）
3. 用一句话说明投票理由

直接输出你的内容，不要加角色名前缀。
"""

# Diverse audience profiles
AUDIENCE_PROFILES = [
    {"name": "小李", "background": "理工科大学生，重视数据和逻辑"},
    {"name": "张姐", "background": "资深媒体人，关注社会影响和舆论"},
    {"name": "王叔", "background": "退休教师，看重教育意义和人文关怀"},
    {"name": "小陈", "background": "创业者，务实主义，关注可行性"},
    {"name": "赵同学", "background": "哲学研究生，喜欢追问本质和前提假设"},
]


class Audience(BaseAgent):
    """An audience member who reacts and votes."""

    def __init__(self, profile: dict, topic: str):
        system_prompt = AUDIENCE_PROMPT.format(
            name=profile["name"],
            background=profile["background"],
            topic=topic,
        )
        super().__init__(name=profile["name"], system_prompt=system_prompt)

    def vote(self, debate_transcript: str) -> str:
        prompt = f"""以下是完整的辩论记录：

{debate_transcript}

请给出你的评论和投票。按以下格式：
- 印象最深的论点：...
- 我的投票：正方/反方
- 投票理由：..."""
        return self.speak(prompt)
