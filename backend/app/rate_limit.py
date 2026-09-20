"""A small fixed-window rate limiter for the paid endpoints.

`/api/query` spends real money: 3 LLM calls, about $0.0007 a query. The demo URL
is public and unauthenticated, so without a cap a loop costs whatever someone
feels like spending. Cloud Run's `max-instances: 3` caps the compute bill but
says nothing about the Groq bill.

In-process and per-instance on purpose. A shared counter means Redis, which is a
service to run, pay for and keep alive for a demo that scales to zero. With
max-instances 3 the real ceiling is 3x what is configured here, which is
accounted for in the number chosen rather than pretended away.

Fixed window, not a sliding one: a burst straddling a boundary can briefly send
double the rate. That is fine for cost control, where the goal is stopping a
runaway loop, not precise fairness.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        """Off when `DISABLE_RATE_LIMIT=true`.

        The test suite shares one process and one client address, so every test
        that posts an upload counts against the same bucket and the later ones
        get a 429 that has nothing to do with what they are testing. Read at
        call time rather than at construction so a test can flip it per-case.
        """
        import os

        return os.getenv("DISABLE_RATE_LIMIT", "").lower() not in {"1", "true", "yes"}

    def allow(self, key: str) -> bool:
        """True if this caller is under the limit. Records the hit when it is."""
        if not self.enabled:
            return True
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            # Drop the key entirely when it empties, so a stream of one-off IPs
            # cannot grow this dict forever.
            if not hits and key in self._hits and len(self._hits) > 1024:
                self._hits.pop(key, None)
                hits = self._hits[key]
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest hit in the window expires."""
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 0
            return max(1, int(self.window - (time.monotonic() - hits[0])))
