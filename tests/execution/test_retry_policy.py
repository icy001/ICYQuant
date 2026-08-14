from services.execution.domain.retry import (
    RetryPolicy,
)


def test_exponential_backoff():

    policy = RetryPolicy(
        max_attempts=5,
        initial_delay_seconds=1,
        max_delay_seconds=60,
        multiplier=2,
    )

    assert policy.delay_for(1) == 1
    assert policy.delay_for(2) == 2
    assert policy.delay_for(3) == 4
    assert policy.delay_for(4) == 8


def test_backoff_is_capped():

    policy = RetryPolicy(
        max_attempts=10,
        initial_delay_seconds=10,
        max_delay_seconds=30,
        multiplier=2,
    )

    assert policy.delay_for(5) == 30


def test_delay_for_rejects_non_positive_attempt():

    policy = RetryPolicy()

    import pytest

    with pytest.raises(ValueError):
        policy.delay_for(0)


def test_validate_rejects_bad_policy():

    import pytest

    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0).validate()

    with pytest.raises(ValueError):
        RetryPolicy(initial_delay_seconds=-1).validate()

    with pytest.raises(ValueError):
        RetryPolicy(max_delay_seconds=-1).validate()

    with pytest.raises(ValueError):
        RetryPolicy(multiplier=0.5).validate()
