"""Knowledge retriever that finds relevant knowledge entries for a given context.

Uses keyword matching with simple TF scoring. Lightweight, no external dependencies.
"""

import re
from collections import Counter
from knowledge.schema import KnowledgeEntry, AgentProfile


def _tokenize(text: str) -> list[str]:
    """Simple Chinese + English tokenizer.

    Splits on non-word characters and extracts individual Chinese characters
    as well as English words. Good enough for keyword matching.
    """
    # Extract English words
    english = re.findall(r'[a-zA-Z]{2,}', text.lower())
    # Extract Chinese characters and common 2-char combinations
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    # Build 2-gram for Chinese text
    chinese_text = re.findall(r'[\u4e00-\u9fff]+', text)
    bigrams = []
    for segment in chinese_text:
        for i in range(len(segment) - 1):
            bigrams.append(segment[i:i+2])
    return english + chinese_chars + bigrams


def retrieve(
    profile: AgentProfile,
    context: str,
    top_k: int = 4,
) -> list[KnowledgeEntry]:
    """Retrieve the most relevant knowledge entries for the given context.

    Scoring: for each knowledge entry, count how many of its keywords
    appear in the context. Entries with higher overlap score higher.

    Args:
        profile: The agent's profile containing knowledge entries.
        context: The current debate context (recent messages).
        top_k: Number of entries to return.

    Returns:
        List of most relevant KnowledgeEntry objects, sorted by relevance.
    """
    if not profile.knowledge:
        return []

    context_tokens = set(_tokenize(context))
    scored: list[tuple[float, KnowledgeEntry]] = []

    for entry in profile.knowledge:
        score = 0.0

        # Score from explicit keywords
        for kw in entry.keywords:
            kw_lower = kw.lower()
            # Exact keyword match in context (high weight)
            if kw_lower in context.lower():
                score += 3.0
            # Token-level overlap (lower weight)
            elif any(kw_lower in tok for tok in context_tokens):
                score += 1.0

        # Score from domain relevance (check if domain keywords appear)
        domain_tokens = set(_tokenize(entry.domain))
        domain_overlap = len(domain_tokens & context_tokens)
        score += domain_overlap * 0.5

        # Score from content relevance (check content tokens against context)
        content_tokens = set(_tokenize(entry.content))
        content_overlap = len(content_tokens & context_tokens)
        score += content_overlap * 0.1

        scored.append((score, entry))

    # Sort by score descending, take top_k
    scored.sort(key=lambda x: x[0], reverse=True)

    # Only return entries with positive score; if none match, return top entries anyway
    results = [entry for score, entry in scored[:top_k] if score > 0]
    if not results and profile.knowledge:
        # Fallback: return top_k entries even without match (better than nothing)
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
