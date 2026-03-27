"""Judge agent that evaluates the debate."""

from agents.base import BaseAgent

JUDGE_PROMPT = """你是一位专业的辩论赛评委。

## 辩题
{topic}

## 你的评判标准
1. **论点质量**（30分）：论点是否有深度、有说服力
2. **逻辑严密性**（25分）：论证过程是否逻辑自洽、推理合理
3. **回应能力**（25分）：是否有效回应了对方的论点和质疑
4. **表达与风度**（20分）：语言表达是否清晰有力、是否保持风度

## 评判规则
- 保持绝对中立和客观
- 对每一方分别打分（满分100分）
- 指出双方的亮点和不足
- 给出最终胜负判定
- 直接输出你的点评内容，不要加角色名前缀
"""


class Judge(BaseAgent):
    """Judge agent that scores and evaluates the debate."""

    def __init__(self, topic: str):
        system_prompt = JUDGE_PROMPT.format(topic=topic)
        super().__init__(name="评委", system_prompt=system_prompt)

    def evaluate(self, debate_transcript: str) -> str:
        prompt = f"""以下是完整的辩论记录：

{debate_transcript}

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
        return self.speak(prompt)
