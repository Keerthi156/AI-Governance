"""
Intelligent Task Router.

Why this exists:
- Enterprises need automatic model selection by workload type.
- Rule-based classification is deterministic, free, and auditable (governance-friendly).
- Recommendations prefer configured free-tier providers when available.

Approach (recommended for v1):
- Heuristic classifier + ranked candidate catalog + preference weights.
- Optional execute path reuses existing llm_service.run_completion.
- LLM-as-classifier can be added later as a strategy without changing the API.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.models.routing import RoutingDecision
from app.services.llm_service import CompletionOutcome, run_completion
from app.services.organization_service import get_or_create_organization
from app.services.provider_registry import SUPPORTED_PROVIDERS

TASK_TYPES = (
    "coding",
    "summarization",
    "creative",
    "qa",
    "analysis",
    "translation",
    "chat",
    "general",
)

PREFERENCES = ("balanced", "cost", "speed", "quality")

# Ranked catalogs: first items preferred for that task under balanced preference.
TASK_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "coding": [
        ("groq", "llama-3.3-70b-versatile"),
        ("groq", "llama-3.1-8b-instant"),
        ("openai", "gpt-4o-mini"),
        ("claude", "claude-3-5-haiku-latest"),
        ("gemini", "gemini-2.0-flash"),
    ],
    "summarization": [
        ("gemini", "gemini-2.0-flash"),
        ("groq", "llama-3.1-8b-instant"),
        ("openai", "gpt-4o-mini"),
        ("claude", "claude-3-5-haiku-latest"),
    ],
    "creative": [
        ("claude", "claude-3-5-haiku-latest"),
        ("openai", "gpt-4o-mini"),
        ("groq", "llama-3.3-70b-versatile"),
        ("gemini", "gemini-2.0-flash"),
    ],
    "qa": [
        ("groq", "llama-3.1-8b-instant"),
        ("gemini", "gemini-2.0-flash"),
        ("openai", "gpt-4o-mini"),
    ],
    "analysis": [
        ("openai", "gpt-4o-mini"),
        ("claude", "claude-3-5-haiku-latest"),
        ("groq", "llama-3.3-70b-versatile"),
        ("gemini", "gemini-1.5-flash"),
    ],
    "translation": [
        ("gemini", "gemini-2.0-flash"),
        ("groq", "llama-3.1-8b-instant"),
        ("openai", "gpt-4o-mini"),
    ],
    "chat": [
        ("groq", "llama-3.1-8b-instant"),
        ("gemini", "gemini-2.0-flash"),
        ("openai", "gpt-4o-mini"),
    ],
    "general": [
        ("groq", "llama-3.1-8b-instant"),
        ("gemini", "gemini-2.0-flash"),
        ("openai", "gpt-4o-mini"),
        ("claude", "claude-3-5-haiku-latest"),
    ],
}

# Keyword signals → task type (weighted).
SIGNAL_RULES: list[tuple[str, list[re.Pattern[str]], float]] = [
    (
        "coding",
        [
            re.compile(r"\b(code|coding|bug|debug|refactor|function|class|api|sql|regex)\b", re.I),
            re.compile(r"\b(python|javascript|typescript|java|golang|rust|fastapi|react)\b", re.I),
            re.compile(r"```"),
            re.compile(r"\b(stack\s*trace|compile|unit\s*test)\b", re.I),
        ],
        1.0,
    ),
    (
        "summarization",
        [
            re.compile(r"\b(summar(y|ize|ise)|tldr|tl;dr|key\s*points|brief)\b", re.I),
            re.compile(r"\b(condense|shorten|abstract)\b", re.I),
        ],
        1.0,
    ),
    (
        "creative",
        [
            re.compile(r"\b(poem|story|novel|lyrics|brainstorm|creative|slogan|tagline)\b", re.I),
            re.compile(r"\b(write\s+a\s+(blog|essay|script|joke))\b", re.I),
        ],
        1.0,
    ),
    (
        "translation",
        [
            re.compile(r"\b(translate|translation|into\s+(spanish|french|german|hindi|tamil))\b", re.I),
            re.compile(r"\b(from\s+\w+\s+to\s+\w+)\b", re.I),
        ],
        1.2,
    ),
    (
        "analysis",
        [
            re.compile(r"\b(analy[sz]e|analysis|compare|trade-?offs|pros\s+and\s+cons)\b", re.I),
            re.compile(r"\b(evaluate|benchmark|root\s*cause|metrics)\b", re.I),
        ],
        1.0,
    ),
    (
        "qa",
        [
            re.compile(r"^\s*(what|why|how|when|where|who|which)\b", re.I),
            re.compile(r"\?\s*$"),
            re.compile(r"\b(explain|define|difference between)\b", re.I),
        ],
        0.8,
    ),
    (
        "chat",
        [
            re.compile(r"^\s*(hi|hello|hey|thanks|thank you)\b", re.I),
            re.compile(r"\b(how are you|good morning)\b", re.I),
        ],
        0.9,
    ),
]


@dataclass(frozen=True)
class ClassificationResult:
    task_type: str
    confidence: float
    matched_signals: list[str]
    scores: dict[str, float]


@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    model: str
    score: float
    available: bool
    reason: str


@dataclass(frozen=True)
class RouteOutcome:
    decision_id: str
    task_type: str
    confidence: float
    preference: str
    recommended_provider: str
    recommended_model: str
    rationale: str
    matched_signals: list[str]
    candidates: list[RouteCandidate]
    executed: bool
    completion: CompletionOutcome | None


def configured_providers() -> set[str]:
    """Return providers that currently have API keys configured."""
    settings = get_settings()
    available: set[str] = set()
    if settings.groq_api_key:
        available.add("groq")
    if settings.google_api_key:
        available.add("gemini")
    if settings.openai_api_key:
        available.add("openai")
    if settings.anthropic_api_key:
        available.add("claude")
    return available & set(SUPPORTED_PROVIDERS)


def classify_prompt(prompt: str) -> ClassificationResult:
    """Classify prompt into a task type using weighted keyword signals."""
    cleaned = prompt.strip()
    if not cleaned:
        raise ValidationAppError("Prompt must not be empty.")

    scores: dict[str, float] = {task: 0.0 for task in TASK_TYPES}
    matched: list[str] = []

    for task_type, patterns, weight in SIGNAL_RULES:
        for pattern in patterns:
            found = pattern.findall(cleaned)
            if found:
                hit = pattern.pattern if isinstance(pattern.pattern, str) else str(pattern)
                scores[task_type] += weight
                matched.append(f"{task_type}:{hit}")

    # Length heuristic: long prompts often need summarization/analysis.
    if len(cleaned) > 1200:
        scores["summarization"] += 0.6
        matched.append("heuristic:long_prompt")

    best_task = max(scores.items(), key=lambda item: item[1])[0]
    best_score = scores[best_task]
    if best_score <= 0:
        return ClassificationResult(
            task_type="general",
            confidence=0.35,
            matched_signals=["fallback:general"],
            scores=scores,
        )

    total = sum(scores.values()) or 1.0
    confidence = min(0.98, max(0.4, best_score / total))
    return ClassificationResult(
        task_type=best_task,
        confidence=round(confidence, 4),
        matched_signals=matched[:12],
        scores=scores,
    )


def _preference_bonus(provider: str, model: str, preference: str, rank: int) -> float:
    """Score adjustment by user preference (lower rank index is better)."""
    base = max(0.0, 10.0 - rank)
    free = provider in {"groq", "gemini"}
    premium = provider in {"openai", "claude"}
    fast = "8b" in model or "flash" in model or "instant" in model
    strong = "70b" in model or "gpt-4o" in model or "sonnet" in model or "pro" in model

    if preference == "cost":
        return base + (5.0 if free else 0.0) + (1.0 if fast else 0.0)
    if preference == "speed":
        return base + (4.0 if fast else 0.0) + (2.0 if provider == "groq" else 0.0)
    if preference == "quality":
        return base + (4.0 if premium or strong else 0.0)
    # balanced: slight free-tier bias for demos / enterprise cost control
    return base + (2.0 if free else 0.0) + (1.0 if strong else 0.0)


def rank_candidates(
    *,
    task_type: str,
    preference: str,
    available: set[str] | None = None,
) -> list[RouteCandidate]:
    """Rank provider/model candidates for a task + preference."""
    if preference not in PREFERENCES:
        raise ValidationAppError(
            f"Unsupported preference '{preference}'. Supported: {list(PREFERENCES)}"
        )
    if task_type not in TASK_CANDIDATES:
        task_type = "general"

    available = available if available is not None else configured_providers()
    catalog = TASK_CANDIDATES[task_type]
    ranked: list[RouteCandidate] = []

    for idx, (provider, model) in enumerate(catalog):
        is_available = provider in available
        score = _preference_bonus(provider, model, preference, idx)
        if not is_available:
            score -= 100.0
        ranked.append(
            RouteCandidate(
                provider=provider,
                model=model,
                score=round(score, 4),
                available=is_available,
                reason=(
                    "configured"
                    if is_available
                    else f"{provider} API key not configured"
                ),
            )
        )

    ranked.sort(key=lambda c: c.score, reverse=True)

    # If nothing configured, still return catalog order but mark unavailable.
    if not any(c.available for c in ranked):
        return ranked
    return ranked


def route_prompt(
    db: Session,
    *,
    prompt: str,
    preference: str = "balanced",
    organization_slug: str = "default",
    execute: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> RouteOutcome:
    """
    Classify + recommend (+ optional execute) and persist the routing decision.
    """
    preference_key = preference.strip().lower()
    if preference_key not in PREFERENCES:
        raise ValidationAppError(
            f"Unsupported preference '{preference}'. Supported: {list(PREFERENCES)}"
        )

    cleaned = prompt.strip()
    if not cleaned:
        raise ValidationAppError("Prompt must not be empty.")

    classification = classify_prompt(cleaned)
    candidates = rank_candidates(
        task_type=classification.task_type,
        preference=preference_key,
    )
    available = [c for c in candidates if c.available]
    chosen = available[0] if available else candidates[0]

    rationale = (
        f"Detected task_type='{classification.task_type}' "
        f"(confidence={classification.confidence:.2f}) with preference='{preference_key}'. "
        f"Selected {chosen.provider}/{chosen.model} "
        f"({'available' if chosen.available else 'fallback-unavailable'})."
    )

    org = get_or_create_organization(db, slug=organization_slug)
    decision = RoutingDecision(
        organization_id=org.id,
        prompt=cleaned,
        task_type=classification.task_type,
        confidence=classification.confidence,
        preference=preference_key,
        recommended_provider=chosen.provider,
        recommended_model=chosen.model,
        rationale=rationale,
        candidates=[
            {
                "provider": c.provider,
                "model": c.model,
                "score": c.score,
                "available": c.available,
                "reason": c.reason,
            }
            for c in candidates
        ],
        matched_signals=classification.matched_signals,
        executed=False,
        history_id=None,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    completion: CompletionOutcome | None = None
    if execute:
        if not chosen.available:
            raise ValidationAppError(
                "Cannot execute: recommended provider API key is not configured.",
                details={
                    "provider": chosen.provider,
                    "model": chosen.model,
                },
            )
        completion = run_completion(
            db,
            provider=chosen.provider,
            prompt=cleaned,
            model=chosen.model,
            organization_slug=organization_slug,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        decision.executed = True
        decision.history_id = uuid.UUID(completion.history_id)
        db.add(decision)
        db.commit()
        db.refresh(decision)

    return RouteOutcome(
        decision_id=str(decision.id),
        task_type=decision.task_type,
        confidence=decision.confidence,
        preference=decision.preference,
        recommended_provider=decision.recommended_provider,
        recommended_model=decision.recommended_model,
        rationale=decision.rationale,
        matched_signals=list(decision.matched_signals or []),
        candidates=candidates,
        executed=decision.executed,
        completion=completion,
    )


def classify_only(prompt: str) -> ClassificationResult:
    """Public classify helper (no DB write)."""
    return classify_prompt(prompt)
