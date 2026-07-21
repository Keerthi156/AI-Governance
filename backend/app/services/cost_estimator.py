"""
Static USD pricing per 1M tokens for cost estimation.

Why this exists:
- Governance and dashboards need approximate spend before billing APIs exist.
- Central table avoids hardcoding rates inside route handlers.
- Rates are approximate public list prices; update as providers change pricing.
"""

from decimal import Decimal

# (input_per_1m_usd, output_per_1m_usd)
MODEL_PRICING_USD_PER_1M: dict[str, tuple[Decimal, Decimal]] = {
    # OpenAI
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("1.60")),
    "gpt-4.1": (Decimal("2.00"), Decimal("8.00")),
    "gpt-3.5-turbo": (Decimal("0.50"), Decimal("1.50")),
    # Anthropic
    "claude-3-5-haiku-latest": (Decimal("0.80"), Decimal("4.00")),
    "claude-3-5-sonnet-latest": (Decimal("3.00"), Decimal("15.00")),
    "claude-sonnet-4-20250514": (Decimal("3.00"), Decimal("15.00")),
    "claude-3-haiku-20240307": (Decimal("0.25"), Decimal("1.25")),
    # Google (free tier friendly)
    "gemini-2.0-flash": (Decimal("0.10"), Decimal("0.40")),
    "gemini-2.0-flash-lite": (Decimal("0.075"), Decimal("0.30")),
    "gemini-1.5-flash": (Decimal("0.075"), Decimal("0.30")),
    "gemini-1.5-flash-latest": (Decimal("0.075"), Decimal("0.30")),
    "gemini-1.5-pro": (Decimal("1.25"), Decimal("5.00")),
    # Groq (often free-tier; list rates for estimation)
    "llama-3.3-70b-versatile": (Decimal("0.59"), Decimal("0.79")),
    "llama-3.1-8b-instant": (Decimal("0.05"), Decimal("0.08")),
    "llama-3.1-70b-versatile": (Decimal("0.59"), Decimal("0.79")),
    "gemma2-9b-it": (Decimal("0.20"), Decimal("0.20")),
    "mixtral-8x7b-32768": (Decimal("0.24"), Decimal("0.24")),
}

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_CLAUDE_MODEL = "claude-3-5-haiku-latest"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"

DEFAULT_MODELS = {
    "groq": DEFAULT_GROQ_MODEL,
    "gemini": DEFAULT_GEMINI_MODEL,
    "openai": DEFAULT_OPENAI_MODEL,
    "claude": DEFAULT_CLAUDE_MODEL,
}


def estimate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> Decimal | None:
    """
    Estimate USD cost from token counts.

    Returns None when the model is unknown (still persist tokens; cost optional).
    """
    rates = MODEL_PRICING_USD_PER_1M.get(model)
    if rates is None:
        for key, value in MODEL_PRICING_USD_PER_1M.items():
            if model.startswith(key) or key.startswith(model):
                rates = value
                break
    if rates is None:
        return None

    input_rate, output_rate = rates
    input_cost = (Decimal(prompt_tokens) / Decimal(1_000_000)) * input_rate
    output_cost = (Decimal(completion_tokens) / Decimal(1_000_000)) * output_rate
    return (input_cost + output_cost).quantize(Decimal("0.000001"))
