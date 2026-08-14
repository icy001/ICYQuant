"""Recovery engine — determine, reconcile, then decide retry (§19-29)."""

from __future__ import annotations

import pytest

from services.control_plane.errors import ControlErrorCode
from services.control_plane.execution_attempt import ExecutionState
from services.control_plane.recovery_engine import ControlRecovery, RecoveryAction
from services.control_plane.timeout import RetryPolicy


def _policy(**overrides):
    base = dict(
        max_attempts=3,
        retryable_errors=(ControlErrorCode.TIMEOUT_ERROR.value,),
    )
    base.update(overrides)
    return RetryPolicy(**base)


def test_unknown_attempt_is_reconciled_not_retried(make_command, make_attempt):
    """§16/§40: UNKNOWN never blind-retries — the target must be checked first."""
    recovery = ControlRecovery(retry_policy=_policy())
    command = make_command()
    attempt = make_attempt(state=ExecutionState.UNKNOWN)
    decision = recovery.recover(command, attempt)
    assert decision.action == RecoveryAction.RECONCILE.value
    assert decision.state == "RECOVERY_REQUIRED"


def test_timed_out_attempt_is_reconciled(make_command, make_attempt):
    recovery = ControlRecovery(retry_policy=_policy())
    attempt = make_attempt(state=ExecutionState.TIMED_OUT)
    decision = recovery.recover(make_command(), attempt)
    assert decision.action == RecoveryAction.RECONCILE.value


def test_failed_attempt_without_policy_is_manual(make_command, make_attempt):
    recovery = ControlRecovery(retry_policy=None)
    attempt = make_attempt(
        state=ExecutionState.FAILED,
        error_code=ControlErrorCode.EXECUTION_ERROR.value,
    )
    decision = recovery.recover(make_command(), attempt)
    assert decision.action == RecoveryAction.MANUAL_INTERVENTION.value


def test_failed_attempt_with_retryable_error_retries(make_command, make_attempt):
    recovery = ControlRecovery(retry_policy=_policy())
    attempt = make_attempt(
        attempt_number=1,
        state=ExecutionState.FAILED,
        error_code=ControlErrorCode.TIMEOUT_ERROR.value,
    )
    decision = recovery.recover(make_command(), attempt)
    assert decision.action == RecoveryAction.RETRY.value
    assert decision.state == "AUTHORIZED"


def test_failed_attempt_at_max_attempts_stops(make_command, make_attempt):
    recovery = ControlRecovery(retry_policy=_policy(max_attempts=1))
    attempt = make_attempt(
        attempt_number=1,
        state=ExecutionState.FAILED,
        error_code=ControlErrorCode.TIMEOUT_ERROR.value,
    )
    decision = recovery.recover(make_command(), attempt)
    assert decision.action == RecoveryAction.MANUAL_INTERVENTION.value


def test_succeeded_attempt_needs_no_action(make_command, make_attempt):
    recovery = ControlRecovery()
    attempt = make_attempt(state=ExecutionState.SUCCEEDED)
    decision = recovery.recover(make_command(), attempt)
    assert decision.action == RecoveryAction.NO_ACTION.value


def test_reconcile_applied_target_succeeds(make_command):
    """§21/§41: target already PAUSED -> SUCCEEDED."""
    recovery = ControlRecovery(applied_targets={"trading:pause": "PAUSED"})
    decision = recovery.reconcile(make_command(), "PAUSED")
    assert decision.action == RecoveryAction.SUCCEED.value
    assert decision.state == "SUCCEEDED"


def test_reconcile_not_applied_without_policy_is_manual(make_command):
    recovery = ControlRecovery(
        retry_policy=None,
        applied_targets={"trading:pause": "PAUSED"},
    )
    decision = recovery.reconcile(make_command(), "RUNNING")
    assert decision.action == RecoveryAction.MANUAL_INTERVENTION.value


def test_reconcile_not_applied_with_policy_may_retry(make_command):
    recovery = ControlRecovery(
        retry_policy=_policy(),
        applied_targets={"trading:pause": "PAUSED"},
    )
    decision = recovery.reconcile(make_command(), "RUNNING")
    assert decision.action == RecoveryAction.RETRY.value


def test_reconcile_without_mapping_is_manual(make_command):
    """No mapping configured -> cannot determine -> MANUAL_INTERVENTION (§26)."""
    recovery = ControlRecovery()
    decision = recovery.reconcile(make_command(), "PAUSED")
    assert decision.action == RecoveryAction.MANUAL_INTERVENTION.value


def test_reconcile_explicit_applied_flag(make_command):
    recovery = ControlRecovery()
    decision = recovery.reconcile(make_command(), "PAUSED", applied=True)
    assert decision.action == RecoveryAction.SUCCEED.value
