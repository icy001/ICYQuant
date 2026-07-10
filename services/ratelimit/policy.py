"""
Rate limit policies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
)
class RateLimitPolicy:
    __slots__ = (
        "name",
        "max_requests",
        "window_seconds",
    )
    name: str
    max_requests: int
    window_seconds: int


DEFAULT_POLICIES = {
    "default":
    RateLimitPolicy(
        name="default",
        max_requests=100,
        window_seconds=60
    ),
    "trading":
    RateLimitPolicy(
        name="trading",
        max_requests=20,
        window_seconds=60
    ),
    "repair":
    RateLimitPolicy(
        name="repair",
        max_requests=5,
        window_seconds=60
    ),
    "approval":
    RateLimitPolicy(
        name="approval",
        max_requests=10,
        window_seconds=60
    ),
    "admin":
    RateLimitPolicy(
        name="admin",
        max_requests=10,
        window_seconds=60
    )
}