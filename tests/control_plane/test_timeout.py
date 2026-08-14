"""Execution timeout and retry policy (§14, §27-29)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.errors import ControlErrorCode
from services.control_plane.timeout import ExecutionTimeout, RetryPolicy


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def test_timeout_not_expired_within_window():
    timeout = ExecutionTimeout(timeout_seconds=10, retryable=False)
    assert not timeout.is_expired(_utc() - timedelta(seconds=5), now=_utc())


def test_timeout_expired_after_window():
    timeout = ExecutionTimeout(timeout_seconds=10, retryable=False)
    assert timeout.is_expired(_utc() - timedelta(seconds=11), now=_utc())


def test_different_commands_can_have_different_timeouts():
    pause = ExecutionTimeout(timeout_seconds=10, retryable=True)
    repair = ExecutionTimeout(timeout_seconds=300, retryable=False)
    assert pause.timeout_seconds == 10
    assert repair.timeout_seconds == 300


def test_retry_policy_defaults_to_no_unknown_retry():
    policy = RetryPolicy(max_attempts=3)
    assert policy.allow_unknown_retry is False
    assert not policy.is_retryable(None)
    assert not policy.can_retry(1, None)


def test_retry_policy_respects_max_attempts():
    policy = RetryPolicy(
        max_attempts=2,
        retryable_errors=(ControlErrorCode.TIMEOUT_ERROR.value,),
    )
    assert policy.can_retry(1, ControlErrorCode.TIMEOUT_ERROR.value)
    assert not policy.can_retry(2, ControlErrorCode.TIMEOUT_ERROR.value)


def test_retry_policy_only_retries_known_errors():
    policy = RetryPolicy(
        max_attempts=5,
        retryable_errors=(ControlErrorCode.TIMEOUT_ERROR.value,),
    )
    assert policy.is_retryable(ControlErrorCode.TIMEOUT_ERROR.value)
    assert not policy.is_retryable(ControlErrorCode.EXECUTION_ERROR.value)


def test_allow_unknown_retry_is_explicit_opt_in():
    policy = RetryPolicy(max_attempts=3, allow_unknown_retry=True)
    assert policy.is_retryable(None)
    assert policy.can_retry(1, None)
