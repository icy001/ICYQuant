"""
Rate limit middleware service.
"""

from __future__ import annotations

from .limiter import (
    RateLimiter,
)


class RateLimitService:
    def __init__(
        self,
        limiter=None,
    ):
        self.limiter = (
            limiter
            or
            RateLimiter()
        )

    def check(
        self,
        identity: str,
        policy,
    ):
        return self.limiter.allow(
            identity,
            policy.max_requests,
            policy.window_seconds
        )