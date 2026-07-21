"""
Embedding helpers for RAG.

Why this exists:
- Prefer OpenAI embeddings when configured.
- Fall back to a deterministic local hashed bag-of-words vector so RAG works
  without embedding API quota (common on local Windows demos).
"""

from __future__ import annotations

import hashlib
import logging
import math
import re

from app.core.config import get_settings

logger = logging.getLogger("app.rag.embeddings")

LOCAL_DIM = 384
LOCAL_MODEL = "local-hash-v1"
OPENAI_MODEL = "text-embedding-3-small"
OPENAI_DIM = 1536

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm <= 0:
        return vector
    return [v / norm for v in vector]


def local_embed(text: str, dim: int = LOCAL_DIM) -> list[float]:
    """Deterministic sparse-ish hashed embedding (no external API)."""
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    return _l2_normalize(vec)


def openai_embed_many(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API."""
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=OPENAI_MODEL, input=texts)
    # API may not preserve order in theory; sort by index.
    ordered = sorted(response.data, key=lambda item: item.index)
    return [_l2_normalize(list(item.embedding)) for item in ordered]


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    """
    Embed a batch of texts.

    Returns (vectors, embedding_model_name).
    """
    cleaned = [t.strip() if t.strip() else " " for t in texts]
    settings = get_settings()
    if settings.rag_prefer_openai_embeddings and settings.openai_api_key:
        try:
            vectors = openai_embed_many(cleaned)
            return vectors, settings.openai_embedding_model or OPENAI_MODEL
        except Exception:  # noqa: BLE001
            logger.warning(
                "OpenAI embeddings failed; falling back to local-hash",
                exc_info=True,
            )

    return [local_embed(t) for t in cleaned], LOCAL_MODEL


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity for equal-length L2-normalized (or raw) vectors."""
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    if len(a) != len(b):
        # Different embedding spaces are not comparable — score 0.
        return 0.0
    return float(sum(a[i] * b[i] for i in range(n)))
