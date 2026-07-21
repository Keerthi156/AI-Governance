"""
Enhanced evaluation metrics and strategy weights.

Why enhanced heuristics (not LLM-as-judge yet):
- Deterministic, free, auditable for governance.
- Task-aware weights align scoring with router task types.
- LLM-as-judge can plug in later as strategy='llm_judge'.
"""

from __future__ import annotations

import re
from decimal import Decimal

STRATEGIES: dict[str, dict[str, Decimal]] = {
    "balanced": {
        "success": Decimal("0.30"),
        "latency": Decimal("0.20"),
        "cost": Decimal("0.20"),
        "substance": Decimal("0.15"),
        "structure": Decimal("0.10"),
        "relevance": Decimal("0.05"),
    },
    "cheapest": {
        "success": Decimal("0.25"),
        "latency": Decimal("0.10"),
        "cost": Decimal("0.45"),
        "substance": Decimal("0.10"),
        "structure": Decimal("0.05"),
        "relevance": Decimal("0.05"),
    },
    "fastest": {
        "success": Decimal("0.25"),
        "latency": Decimal("0.45"),
        "cost": Decimal("0.10"),
        "substance": Decimal("0.10"),
        "structure": Decimal("0.05"),
        "relevance": Decimal("0.05"),
    },
    "quality": {
        "success": Decimal("0.25"),
        "latency": Decimal("0.05"),
        "cost": Decimal("0.05"),
        "substance": Decimal("0.25"),
        "structure": Decimal("0.20"),
        "relevance": Decimal("0.20"),
    },
    "reliability": {
        "success": Decimal("0.55"),
        "latency": Decimal("0.15"),
        "cost": Decimal("0.10"),
        "substance": Decimal("0.10"),
        "structure": Decimal("0.05"),
        "relevance": Decimal("0.05"),
    },
}

# Task-aware overlays (multipliers applied to base weights, then renormalized).
TASK_WEIGHT_HINTS: dict[str, dict[str, Decimal]] = {
    "coding": {
        "structure": Decimal("1.8"),
        "relevance": Decimal("1.3"),
        "substance": Decimal("1.1"),
    },
    "summarization": {
        "substance": Decimal("1.6"),
        "relevance": Decimal("1.4"),
        "cost": Decimal("1.2"),
    },
    "creative": {
        "substance": Decimal("1.5"),
        "structure": Decimal("1.2"),
        "latency": Decimal("0.8"),
    },
    "analysis": {
        "relevance": Decimal("1.5"),
        "substance": Decimal("1.4"),
        "structure": Decimal("1.2"),
    },
    "qa": {
        "relevance": Decimal("1.6"),
        "latency": Decimal("1.2"),
        "cost": Decimal("1.1"),
    },
    "translation": {
        "relevance": Decimal("1.5"),
        "substance": Decimal("1.2"),
    },
    "chat": {
        "latency": Decimal("1.4"),
        "cost": Decimal("1.3"),
        "success": Decimal("1.2"),
    },
    "general": {},
}


def resolve_weights(strategy: str, task_type: str | None) -> dict[str, Decimal]:
    base = STRATEGIES.get(strategy)
    if base is None:
        raise KeyError(strategy)
    weights = dict(base)
    hints = TASK_WEIGHT_HINTS.get((task_type or "general").lower(), {})
    for key, factor in hints.items():
        if key in weights:
            weights[key] = weights[key] * factor
    total = sum(weights.values()) or Decimal("1")
    return {k: (v / total) for k, v in weights.items()}


def clamp01(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 1:
        return Decimal("1")
    return value


def normalize_inverse(values: list[Decimal | None]) -> list[Decimal]:
    present = [v for v in values if v is not None]
    if not present:
        return [Decimal("0") for _ in values]
    lo = min(present)
    hi = max(present)
    if hi == lo:
        return [Decimal("1") if v is not None else Decimal("0.5") for v in values]
    scores: list[Decimal] = []
    for v in values:
        if v is None:
            scores.append(Decimal("0.5"))
        else:
            scores.append(clamp01((hi - v) / (hi - lo)))
    return scores


def substance_score(status: str, response: str | None) -> Decimal:
    if status != "success" or not response:
        return Decimal("0")
    length = len(response.strip())
    if length < 20:
        return Decimal("0.25")
    if length < 80:
        return Decimal("0.55")
    if length < 400:
        return Decimal("0.85")
    if length < 2000:
        return Decimal("1.00")
    # Extremely long responses get a mild penalty (verbosity).
    return Decimal("0.90")


def structure_score(status: str, response: str | None) -> Decimal:
    """Reward lists, headings, code fences — useful for coding/analysis outputs."""
    if status != "success" or not response:
        return Decimal("0")
    text = response.strip()
    score = Decimal("0.20")
    if re.search(r"(^|\n)\s*([-*]|\d+\.)\s+", text):
        score += Decimal("0.25")
    if re.search(r"(^|\n)#{1,3}\s+\S+", text) or re.search(r"\*\*[^*]+\*\*", text):
        score += Decimal("0.15")
    if "```" in text:
        score += Decimal("0.25")
    if "\n" in text:
        score += Decimal("0.15")
    return clamp01(score)


_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "is",
    "are",
    "be",
    "this",
    "that",
    "with",
    "as",
    "by",
    "it",
    "at",
    "from",
}


def relevance_score(status: str, prompt: str, response: str | None) -> Decimal:
    """Simple token-overlap relevance between prompt and response."""
    if status != "success" or not response:
        return Decimal("0")
    prompt_tokens = {
        t
        for t in re.findall(r"[a-z0-9_]{3,}", prompt.lower())
        if t not in _STOPWORDS
    }
    if not prompt_tokens:
        return Decimal("0.50")
    response_tokens = set(re.findall(r"[a-z0-9_]{3,}", response.lower()))
    overlap = len(prompt_tokens & response_tokens)
    ratio = Decimal(overlap) / Decimal(len(prompt_tokens))
    return clamp01(ratio)
