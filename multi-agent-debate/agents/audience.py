"""Audience agents that vote using value-weighted dimension scoring."""

import json
import re
from dataclasses import dataclass, field

from agents.base import BaseAgent
from knowledge.schema import AudienceProfile


# ---------------------------------------------------------------------------
# Structured vote result
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """Score for a single value dimension."""
    dimension: str
    pro_score: float  # 1-10
    con_score: float  # 1-10


@dataclass
class AudienceVoteResult:
    """Structured vote result from one audience member."""
    voter_name: str
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    weighted_pro: float = 0.0
    weighted_con: float = 0.0
    vote: str = ""  # "正方" or "反方"
    comment: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Default audience profiles (used when value_dims not available)
# ---------------------------------------------------------------------------

DEFAULT_AUDIENCE_PROFILES = [
    AudienceProfile(
        name="小李",
        background="理工科大学生，重视数据和逻辑",
        decision_weights={},  # will be populated per-debate
    ),
    AudienceProfile(
        name="张姐",
        background="资深媒体人，关注社会影响和舆论",
        decision_weights={},
    ),
    AudienceProfile(
        name="王叔",
        background="退休教师，看重教育意义和人文关怀",
        decision_weights={},
    ),
    AudienceProfile(
        name="小陈",
        background="创业者，务实主义，关注可行性",
        decision_weights={},
    ),
    AudienceProfile(
        name="赵同学",
        background="哲学研究生，喜欢追问本质和前提假设",
        decision_weights={},
    ),
]


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

AUDIENCE_VOTE_PROMPT = """你是辩论赛的一名观众，名叫{name}。

## 你的背景
{background}

## 你的价值倾向
你在以下价值维度上的关注度（权重）：
{weights_desc}

## 辩题
{topic}

## 你的任务
观看辩论后，请对正方和反方在每个价值维度上的表现分别打分（1-10分），然后根据你的价值权重计算加权得分，决定你的投票。

**严格按照以下JSON格式输出，不要输出其他内容：**

```json
{{
  "dimension_scores": [
    {{"dimension": "{dim_placeholder_0}", "pro_score": 7, "con_score": 6}},
    {{"dimension": "{dim_placeholder_1}", "pro_score": 5, "con_score": 8}},
    {{"dimension": "{dim_placeholder_2}", "pro_score": 6, "con_score": 7}}
  ],
  "comment": "你印象最深的论点（1-2句话）",
  "vote": "正方或反方（加权得分较高的一方）",
  "reason": "一句话投票理由"
}}
```"""


# ---------------------------------------------------------------------------
# Audience agent
# ---------------------------------------------------------------------------

class Audience(BaseAgent):
    """An audience member who votes using value-weighted dimension scoring."""

    def __init__(self, profile: AudienceProfile, topic: str, value_dims: list[str]):
        self.profile = profile
        self.value_dims = value_dims

        # Build dimension placeholders for prompt
        dim_placeholders = {f"dim_placeholder_{i}": d for i, d in enumerate(value_dims[:3])}

        system_prompt = AUDIENCE_VOTE_PROMPT.format(
            name=profile.name,
            background=profile.background,
            weights_desc=profile.weights_description(),
            topic=topic,
            **dim_placeholders,
        )
        super().__init__(name=profile.name, system_prompt=system_prompt)

    def vote(self, debate_transcript: str) -> tuple[str, AudienceVoteResult | None]:
        """Vote on the debate, returning (raw_text, structured_result).

        Returns:
            (raw_content, AudienceVoteResult or None if parsing fails)
        """
        prompt = f"""以下是完整的辩论记录：

{debate_transcript}

请根据你的价值倾向，对正方和反方在每个价值维度上的表现打分，并给出你的投票。
严格输出JSON，不要输出其他内容。"""

        raw = self.speak(prompt)
        result = self._parse_vote(raw)
        return raw, result

    def _parse_vote(self, raw: str) -> AudienceVoteResult | None:
        """Parse the structured vote from LLM output."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if not json_match:
                return None

            json_str = json_match.group()
            # Fix trailing commas
            json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
            data = json.loads(json_str)

            # Build dimension scores
            dim_scores = []
            for ds in data.get("dimension_scores", []):
                dim_scores.append(DimensionScore(
                    dimension=ds["dimension"],
                    pro_score=float(ds["pro_score"]),
                    con_score=float(ds["con_score"]),
                ))

            # Calculate weighted scores
            weights = self.profile.decision_weights
            weighted_pro = 0.0
            weighted_con = 0.0
            for ds in dim_scores:
                w = weights.get(ds.dimension, 0.0)
                weighted_pro += ds.pro_score * w
                weighted_con += ds.con_score * w

            # Determine vote from weighted scores (override LLM's vote if inconsistent)
            computed_vote = "正方" if weighted_pro >= weighted_con else "反方"

            return AudienceVoteResult(
                voter_name=self.profile.name,
                dimension_scores=dim_scores,
                weights=weights,
                weighted_pro=round(weighted_pro, 2),
                weighted_con=round(weighted_con, 2),
                vote=computed_vote,
                comment=data.get("comment", ""),
                reason=data.get("reason", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# Audience profile generation for custom debates
# ---------------------------------------------------------------------------

def assign_audience_weights(
    value_dims: list[str],
    profiles: list[AudienceProfile] | None = None,
) -> list[AudienceProfile]:
    """Assign diversified value weights to audience profiles.

    Creates 5 audience members with different weight distributions
    so they represent a diverse range of value priorities.
    """
    if profiles is None:
        profiles = [AudienceProfile(name=p.name, background=p.background) for p in DEFAULT_AUDIENCE_PROFILES]

    if len(value_dims) < 3:
        # Pad to 3 dims
        all_dims = ["效率", "公平", "安全", "创新", "自由", "传统"]
        for d in all_dims:
            if d not in value_dims:
                value_dims.append(d)
            if len(value_dims) >= 3:
                break

    d0, d1, d2 = value_dims[0], value_dims[1], value_dims[2]

    # 5 distinct weight distributions — each audience member emphasizes different values
    weight_presets = [
        {d0: 0.60, d1: 0.25, d2: 0.15},  # Heavy on dim 0
        {d0: 0.15, d1: 0.60, d2: 0.25},  # Heavy on dim 1
        {d0: 0.25, d1: 0.15, d2: 0.60},  # Heavy on dim 2
        {d0: 0.45, d1: 0.45, d2: 0.10},  # Balanced dim 0 + 1
        {d0: 0.33, d1: 0.34, d2: 0.33},  # Even distribution
    ]

    for i, profile in enumerate(profiles):
        profile.decision_weights = weight_presets[i % len(weight_presets)]

    return profiles
