"""
FastAPI rate limit dependency.
"""

from fastapi import (
    HTTPException,
)

from services.ratelimit import (
    RateLimitService,
    DEFAULT_POLICIES,
)


service = RateLimitService()


def trading_rate_limit(
    user_id: str,
):
    allowed = service.check(
        user_id,
        DEFAULT_POLICIES[
            "trading"
        ]
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=
            "Too many requests"
        )

    return True