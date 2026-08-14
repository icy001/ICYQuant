"""Retry policy tests (Commit 33 Part 1.5 #6)."""

from __future__ import annotations

from services.order.engine.outbox.retry import RetryPolicy


def test_defaults():
    policy = RetryPolicy()
    assert policy.max_attempts == 5
    assert policy.base_delay_seconds == 1.0
    assert policy.max_delay_seconds == 60.0


def test_exponential_backoff():
    policy = RetryPolicy()
    assert policy.delay(0) == 1.0
    assert policy.delay(1) == 2.0
    assert policy.delay(2) == 4.0
    assert policy.delay(3) == 8.0


def test_delay_capped_at_max():
    policy = RetryPolicy(max_delay_seconds=10.0)
    assert policy.delay(3) == 8.0
    assert policy.delay(4) == 10.0
    assert policy.delay(10) == 10.0


def test_can_retry_within_budget():
    policy = RetryPolicy(max_attempts=5)
    assert policy.can_retry(0)
    assert policy.can_retry(4)
    assert not policy.can_retry(5)
    assert not policy.can_retry(6)


def test_retry_exhaustion_at_max_attempts():
    policy = RetryPolicy(max_attempts=3)
    assert policy.can_retry(0)
    assert policy.can_retry(1)
    assert policy.can_retry(2)
    assert not policy.can_retry(3)
