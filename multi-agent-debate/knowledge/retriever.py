"""Knowledge retriever that finds relevant knowledge entries for a given context.

Scoring consists of three components:
  1. Keyword relevance  — does the knowledge match the current debate context?
  2. Value alignment    — does the knowledge align with the agent's value weights?
  3. Identity relevance — does the knowledge relate to the agent's professional domain?

This creates explicit links between all four layers of the agent profile:
  Identity → professional domain boosts domain-matching knowledge
  Values   → decision_weights prioritize value-aligned knowledge
  Knowledge → entries are scored and selected
  Behavior  → (handled at prompt level, not in retrieval)
"""

import re
from knowledge.schema import KnowledgeEntry, AgentProfile


# === Tokenizer ===

def _tokenize(text: str) -> set[str]:
    """Simple Chinese + English tokenizer. Returns a set of tokens."""
    english = re.findall(r'[a-zA-Z]{2,}', text.lower())
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    chinese_text = re.findall(r'[\u4e00-\u9fff]+', text)
    bigrams = []
    for segment in chinese_text:
        for i in range(len(segment) - 1):
            bigrams.append(segment[i:i+2])
    return set(english + chinese_chars + bigrams)


# === Identity → Knowledge link ===

# Maps occupation keywords to related knowledge domains
_OCCUPATION_DOMAIN_MAP = {
    "研究员": ["科学研究", "经济数据", "环境能源"],
    "产品": ["就业市场", "农业科技", "教育公平"],
    "总监": ["就业市场", "经济数据"],
    "政策": ["政策法规", "国家战略", "全球发展"],
    "法学": ["政策法规", "AI偏见", "隐私安全"],
    "伦理": ["AI偏见", "隐私安全", "人类自主性"],
    "哲学": ["人类自主性", "社会影响"],
    "经济": ["就业冲击", "贫富差距", "经济数据"],
    "劳动": ["就业冲击", "贫富差距"],
    "导演": ["社会影响", "技术滥用"],
    "记者": ["社会影响", "技术滥用"],
    "媒体": ["社会影响", "技术滥用"],
}


def _get_identity_domains(profile: AgentProfile) -> set[str]:
    """Extract relevant knowledge domains from agent's identity."""
    domains = set()
    occupation = profile.identity.occupation
    education = profile.identity.education
    combined = f"{occupation} {education}"

    for keyword, related_domains in _OCCUPATION_DOMAIN_MAP.items():
        if keyword in combined:
            domains.update(related_domains)
    return domains


# === Core retrieval ===

def retrieve(
    profile: AgentProfile,
    context: str,
    top_k: int = 4,
) -> list[KnowledgeEntry]:
    """Retrieve the most relevant knowledge entries for the given context.

    Scoring formula:
        score = keyword_score + value_score + identity_score + content_score

    Where:
        keyword_score  = sum of keyword matches against context
        value_score    = sum of agent's decision_weights for matching value dimensions
        identity_score = bonus if knowledge domain matches agent's professional background
        content_score  = token overlap between knowledge content and context
    """
    if not profile.knowledge:
        return []

    context_tokens = _tokenize(context)
    context_lower = context.lower()
    decision_weights = profile.values.decision_weights
    identity_domains = _get_identity_domains(profile)

    scored: list[tuple[float, KnowledgeEntry]] = []

    for entry in profile.knowledge:
        score = 0.0

        # --- 1. Keyword relevance (context ↔ knowledge) ---
        for kw in entry.keywords:
            kw_lower = kw.lower()
            if kw_lower in context_lower:
                score += 3.0
            elif any(kw_lower in tok for tok in context_tokens):
                score += 1.0

        # Domain token overlap
        domain_tokens = _tokenize(entry.domain)
        score += len(domain_tokens & context_tokens) * 0.5

        # Content token overlap
        content_tokens = _tokenize(entry.content)
        score += len(content_tokens & context_tokens) * 0.1

        # --- 2. Value alignment (values → knowledge) ---
        # If this knowledge has value_dimensions, boost by the agent's weight for those dimensions
        if entry.value_dimensions and decision_weights:
            value_boost = sum(
                decision_weights.get(dim, 0) for dim in entry.value_dimensions
            )
            # Normalize: a knowledge entry tagged with all 3 dimensions of a balanced agent
            # would get ~1.0 boost. Scale it to be meaningful relative to keyword scores.
            score += value_boost * 4.0

        # --- 3. Identity relevance (identity → knowledge) ---
        # Bonus if this knowledge's domain matches the agent's professional background
        if entry.domain in identity_domains:
            score += 2.0

        scored.append((score, entry))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Only return entries with positive score; fallback to top entries
    results = [entry for s, entry in scored[:top_k] if s > 0]
    if not results and profile.knowledge:
        results = [entry for _, entry in scored[:top_k]]

    return results


def format_knowledge_for_prompt(entries: list[KnowledgeEntry]) -> str:
    """Format retrieved knowledge entries into a prompt-injectable string."""
    if not entries:
        return ""

    lines = ["## 你的知识储备（可选择性引用）"]
    for i, entry in enumerate(entries, 1):
        lines.append(f"{i}. 【{entry.domain}】{entry.content}")
    return "\n".join(lines)
