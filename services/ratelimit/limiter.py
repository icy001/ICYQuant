"""
Rate limiter implementation.

Production backend:

Redis

Current:

memory implementation
"""

from __future__ import annotations

import time


class RateLimiter:
    def __init__(self):
        self.requests = {}

    def allow(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> bool:
        now = time.time()

        history = (
            self.requests
            .setdefault(
                key,
                []
            )
        )

        history[:] = [
            t
            for t in history
            if now - t < window
        ]

        if len(history) >= limit:
            return False

        history.append(
            now
        )

        return True