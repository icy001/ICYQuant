from services.ratelimit import (
    RateLimiter,
)


def test_rate_limit():
    limiter = RateLimiter()

    assert limiter.allow(
        "user",
        2,
        60
    )

    assert limiter.allow(
        "user",
        2,
        60
    )

    assert not limiter.allow(
        "user",
        2,
        60
    )