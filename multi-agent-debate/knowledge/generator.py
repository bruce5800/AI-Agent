"""Generate agent profiles dynamically for custom debate topics via LLM.

Takes a debate topic and generates complete AgentProfile objects for
6 debaters (3 pro + 3 con), with all four layers populated:
  - Identity (name, age, occupation, education)
  - Values (core_beliefs, decision_weights)
  - Knowledge (domain, content, keywords, value_dimensions)
  - Behavior (style, emotion_tendency, argument_habits, catchphrases)
"""

import json
import re
from openai import OpenAI

from core.config import API_KEY, API_BASE_URL, MODEL_NAME
from knowledge.schema import (
    AgentProfile, Identity, Values, KnowledgeEntry, Behavior,
)

GENERATION_PROMPT = """你是一个辩论赛角色设计师。请根据以下辩题，为6位辩手设计完整的角色画像。

## 辩题
{topic}

## 要求
为正方3位辩手和反方3位辩手各设计画像。每一方包括：
- 一辩（开篇立论）：适合构建论证框架的背景
- 二辩（攻辩质询）：适合质询和反驳的背景
- 三辩（总结陈词）：适合感性升华的背景

## 价值维度说明
请从以下6个价值维度中选择3个最适合该辩题的维度，用于角色的 decision_weights 和知识的 value_dimensions：
可选维度：效率、公平、安全、创新、自由、传统

## 输出格式
严格输出以下JSON格式，不要输出其他内容：

```json
{{
  "value_dims": ["维度1", "维度2", "维度3"],
  "pro": [
    {{
      "name": "正方一辩",
      "age": 30,
      "occupation": "职业",
      "education": "教育背景",
      "role": "正方一辩（开篇立论）",
      "core_beliefs": ["信念1", "信念2"],
      "decision_weights": {{"维度1": 0.4, "维度2": 0.35, "维度3": 0.25}},
      "knowledge": [
        {{
          "content": "一条具体的、可引用的数据或案例（包含来源）",
          "domain": "领域名称",
          "keywords": ["关键词1", "关键词2", "关键词3"],
          "value_dimensions": ["维度1"]
        }}
      ],
      "style": "辩论风格描述",
      "emotion_tendency": "情绪倾向",
      "argument_habits": ["论证习惯1", "论证习惯2"],
      "catchphrases": ["口头禅1", "口头禅2"]
    }}
  ],
  "con": [...]
}}
```

## 注意事项
1. 每位辩手需要3-4条知识条目
2. 知识内容必须具体、有来源感（可以是合理推测的数据，但要像真实引用）
3. 每条知识必须标注 value_dimensions（从选定的3个维度中选1-2个）
4. decision_weights 三个维度之和应约等于1.0
5. 6位辩手的职业背景应该多样化，与辩题相关但各有侧重
6. 正方名字用"正方一辩/二辩/三辩"，反方同理
"""


def _parse_profile(data: dict, stance: str) -> AgentProfile:
    """Parse a single profile dict into an AgentProfile object."""
    knowledge = []
    for k in data.get("knowledge", []):
        knowledge.append(KnowledgeEntry(
            content=k["content"],
            domain=k["domain"],
            keywords=k.get("keywords", []),
            value_dimensions=k.get("value_dimensions", []),
        ))

    return AgentProfile(
        identity=Identity(
            name=data["name"],
            age=data.get("age", 30),
            occupation=data.get("occupation", ""),
            education=data.get("education", ""),
        ),
        role=data["role"],
        stance=stance,
        values=Values(
            core_beliefs=data.get("core_beliefs", []),
            decision_weights=data.get("decision_weights", {}),
        ),
        knowledge=knowledge,
        behavior=Behavior(
            style=data.get("style", ""),
            emotion_tendency=data.get("emotion_tendency", ""),
            argument_habits=data.get("argument_habits", []),
            catchphrases=data.get("catchphrases", []),
        ),
    )


def generate_profiles(topic: str) -> tuple[list[AgentProfile], list[AgentProfile]]:
    """Generate pro and con debater profiles for a given topic.

    Returns:
        (pro_profiles, con_profiles) — each a list of 3 AgentProfile objects.

    Raises:
        ValueError: If LLM response cannot be parsed.
    """
    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "你是JSON生成器。你只输出合法的JSON，不输出任何其他内容。不要使用markdown代码块。",
            },
            {"role": "user", "content": GENERATION_PROMPT.format(topic=topic)},
        ],
        temperature=0.7,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
        else:
            raise ValueError(f"Cannot parse LLM response as JSON:\n{text[:500]}")

    # Clean control characters that LLM sometimes produces
    json_str = re.sub(r'[\x00-\x1f\x7f]', lambda m: ' ' if m.group() not in '\n\r\t' else m.group(), json_str)
    # Fix common LLM JSON issues: trailing commas before } or ]
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Last resort: strip all newlines and try again
        json_str_flat = json_str.replace('\n', ' ').replace('\r', '')
        data = json.loads(json_str_flat)

    pro_profiles = [_parse_profile(p, "正方") for p in data["pro"]]
    con_profiles = [_parse_profile(c, "反方") for c in data["con"]]

    # Validate we got 3 each
    if len(pro_profiles) != 3 or len(con_profiles) != 3:
        raise ValueError(
            f"Expected 3 pro and 3 con profiles, got {len(pro_profiles)} and {len(con_profiles)}"
        )

    return pro_profiles, con_profiles
