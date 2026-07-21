"""
In-memory sliding-window rate limiter.

Why this exists:
- Protects the API from abuse without requiring Redis for v1.
- Process-local (fine for single-instance / Fargate task); swap for Redis later.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Track request timestamps per key inside a fixed window."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Record a hit and return (allowed, remaining, retry_after_seconds).

        remaining is after this hit when allowed; 0 when blocked.
        """
        now = time.monotonic()
        window_start = now - window_seconds

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
                return False, 0, retry_after

            bucket.append(now)
            remaining = max(0, limit - len(bucket))
            return True, remaining, 0

    def prune(self) -> None:
        """Drop empty buckets (optional housekeeping)."""
        with self._lock:
            empty = [key for key, bucket in self._hits.items() if not bucket]
            for key in empty:
                del self._hits[key]


# Process-wide singleton used by middleware.
rate_limiter = InMemoryRateLimiter()
