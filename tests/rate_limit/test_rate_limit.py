from services.rate_limit import *


def test_rate_limit():

    limiter = GlobalLimiter(
        TokenBucket(2)
    )

    service = RateLimiterService(
        LimiterRepository(),
        limiter
    )

    assert service.check()

    assert service.check()

    assert not service.check()
