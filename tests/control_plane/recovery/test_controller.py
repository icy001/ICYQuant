"""
Tests for RecoveryController (Commit 26 Part 1.5,
spec sections 18-19, 29, 32-33).
"""

from uuid import uuid4

import pytest

from services.control_plane.recovery import (
    RecoveryChecks,
    RecoveryController,
    RecoveryTransitionError,
)
from services.control_plane.recovery.audit import (
    RecoveryAuditEventType,
)
from services.control_plane.recovery.state import RecoveryState


def _all_clear() -> RecoveryChecks:
    return RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )


def _broken_reconciliation() -> RecoveryChecks:
    return RecoveryChecks(
        incident_clear=True,
        positions_reconciled=False,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )


def _new_recovery(require_manual_approval: bool = True) -> RecoveryController:
    return RecoveryController(
        require_manual_approval=require_manual_approval,
    )


def _run_full_flow(recovery: RecoveryController) -> None:
    """KILLED -> VALIDATING -> APPROVAL_REQUIRED -> APPROVED -> RESUMING -> COMPLETED."""
    recovery.validate(_all_clear())
    recovery.approve()
    recovery.resume()
    recovery.complete()


# ----------------------------------------------------------------------
# spec section 29: recovery 不能绕过 Kill
# ----------------------------------------------------------------------

def test_recovery_cannot_resume_without_approval():
    recovery = _new_recovery(require_manual_approval=True)

    recovery.validate()

    assert not recovery.allow_resume


def test_recovery_initial_state_is_idle():
    recovery = _new_recovery()

    assert recovery.state is RecoveryState.IDLE
    assert not recovery.allow_resume


# ----------------------------------------------------------------------
# State machine flow
# ----------------------------------------------------------------------

def test_start_moves_to_validating():
    recovery = _new_recovery()

    recovery_id = recovery.start()

    assert recovery.state is RecoveryState.VALIDATING
    assert recovery.recovery_id == recovery_id
    assert recovery.recovery_id is not None


def test_start_emits_validation_started_audit_event():
    recovery = _new_recovery()
    recovery.start()

    assert (
        recovery.audit_trail[-1].event_type
        is RecoveryAuditEventType.RECOVERY_VALIDATION_STARTED
    )


def test_validation_pass_requires_manual_approval_by_default():
    recovery = _new_recovery()

    assert recovery.validate(_all_clear())

    assert recovery.state is RecoveryState.APPROVAL_REQUIRED
    assert not recovery.allow_resume
    # 未批准不能 resume
    with pytest.raises(RecoveryTransitionError):
        recovery.resume()


def test_validation_failure_blocks_recovery():
    recovery = _new_recovery()

    assert not recovery.validate(_broken_reconciliation())

    assert recovery.state is RecoveryState.BLOCKED
    assert not recovery.allow_resume


def test_validation_failure_emits_failed_audit_event():
    recovery = _new_recovery()

    recovery.validate(_broken_reconciliation())

    assert (
        recovery.audit_trail[-1].event_type
        is RecoveryAuditEventType.RECOVERY_VALIDATION_FAILED
    )


def test_recovery_without_manual_approval_can_resume():
    recovery = _new_recovery(require_manual_approval=False)

    assert recovery.validate(_all_clear())

    assert recovery.state is RecoveryState.APPROVED
    assert recovery.allow_resume


def test_approve_moves_to_approved():
    recovery = _new_recovery()
    recovery.validate(_all_clear())

    recovery.approve(
        actor="risk-manager",
        reason="approved after verification",
    )

    assert recovery.state is RecoveryState.APPROVED
    assert recovery.allow_resume
    assert recovery.audit_trail[-1].event_type is (
        RecoveryAuditEventType.RECOVERY_APPROVED
    )


def test_resume_moves_to_resuming():
    recovery = _new_recovery()
    recovery.validate(_all_clear())
    recovery.approve()

    recovery.resume()

    assert recovery.state is RecoveryState.RESUMING
    assert recovery.audit_trail[-1].event_type is (
        RecoveryAuditEventType.RECOVERY_RESUME_STARTED
    )


def test_complete_moves_to_completed():
    recovery = _new_recovery()
    _run_full_flow(recovery)

    assert recovery.state is RecoveryState.COMPLETED
    assert recovery.audit_trail[-1].event_type is (
        RecoveryAuditEventType.RECOVERY_COMPLETED
    )


def test_fail_during_resume_moves_to_failed():
    recovery = _new_recovery()
    recovery.validate(_all_clear())
    recovery.approve()
    recovery.resume()

    recovery.fail(reason="venue went dark during resume")

    assert recovery.state is RecoveryState.FAILED
    assert recovery.audit_trail[-1].event_type is (
        RecoveryAuditEventType.RECOVERY_FAILED
    )


# ----------------------------------------------------------------------
# spec section 32: 幂等性
# ----------------------------------------------------------------------

def test_approve_is_idempotent():
    recovery = _new_recovery()
    recovery.validate(_all_clear())

    recovery.approve()
    recovery.approve()

    assert recovery.state is RecoveryState.APPROVED
    assert [
        r.event_type for r in recovery.audit_trail
    ].count(RecoveryAuditEventType.RECOVERY_APPROVED) == 1


def test_each_recovery_session_has_unique_id():
    recovery = _new_recovery()

    first = recovery.start()
    recovery.validate(_all_clear())
    recovery.approve()
    recovery.resume()
    recovery.complete()

    second = recovery.start()

    assert first != second
    assert recovery.state is RecoveryState.VALIDATING


# ----------------------------------------------------------------------
# spec section 33: 非法状态迁移
# ----------------------------------------------------------------------

def test_cannot_approve_before_validation():
    recovery = _new_recovery()

    with pytest.raises(RecoveryTransitionError):
        recovery.approve()


def test_cannot_resume_from_idle():
    recovery = _new_recovery()

    with pytest.raises(RecoveryTransitionError):
        recovery.resume()


def test_cannot_complete_from_idle():
    recovery = _new_recovery()

    with pytest.raises(RecoveryTransitionError):
        recovery.complete()


def test_cannot_fail_from_idle():
    recovery = _new_recovery()

    with pytest.raises(RecoveryTransitionError):
        recovery.fail()


def test_cannot_start_while_validation_in_progress():
    recovery = _new_recovery()
    recovery.start()

    with pytest.raises(RecoveryTransitionError):
        recovery.start()


def test_cannot_validate_from_completed():
    recovery = _new_recovery()
    _run_full_flow(recovery)

    with pytest.raises(RecoveryTransitionError):
        recovery.validate(_all_clear())


# ----------------------------------------------------------------------
# evaluate()
# ----------------------------------------------------------------------

def test_evaluate_reflects_current_state():
    recovery = _new_recovery()

    idle = recovery.evaluate()
    assert idle.state is RecoveryState.IDLE
    assert not idle.allow_resume

    recovery.validate(_all_clear())
    awaiting = recovery.evaluate()
    assert awaiting.state is RecoveryState.APPROVAL_REQUIRED
    assert not awaiting.allow_resume

    recovery.approve()
    approved = recovery.evaluate()
    assert approved.state is RecoveryState.APPROVED
    assert approved.allow_resume
