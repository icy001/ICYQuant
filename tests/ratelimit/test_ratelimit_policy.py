from services.ratelimit import (
    DEFAULT_POLICIES,
)


def test_trading_policy():
    policy = DEFAULT_POLICIES[
        "trading"
    ]

    assert (
        policy.max_requests
        ==
        20
    )