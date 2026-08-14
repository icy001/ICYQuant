"""State machine transitions (Commit 29 Part 1.3 §3-6)."""

from __future__ import annotations

from services.control_plane.transition import (
    ALLOWED_TRANSITIONS,
    StateTransitionEngine,
)


def test_happy_path_transitions_are_allowed():
    engine = StateTransitionEngine()
    current = "RECEIVED"
    for target in ("AUTHORIZING", "AUTHORIZED", "DISPATCHING", "EXECUTING", "SUCCEEDED"):
        assert engine.transition(current, target) == target
        current = target


def test_authorizing_can_branch_to_approval_path():
    engine = StateTransitionEngine()
    assert engine.transition("AUTHORIZING", "WAITING_APPROVAL") == "WAITING_APPROVAL"
    assert engine.transition("WAITING_APPROVAL", "AUTHORIZED") == "AUTHORIZED"


def test_authorizing_can_reject():
    engine = StateTransitionEngine()
    assert engine.transition("AUTHORIZING", "REJECTED") == "REJECTED"


def test_received_can_cancel():
    engine = StateTransitionEngine()
    assert engine.transition("RECEIVED", "CANCELLED") == "CANCELLED"


def test_authorized_can_cancel():
    engine = StateTransitionEngine()
    assert engine.transition("AUTHORIZED", "CANCELLED") == "CANCELLED"


def test_failed_can_retry_after_authorization():
    engine = StateTransitionEngine()
    assert engine.transition("FAILED", "AUTHORIZED") == "AUTHORIZED"
    assert engine.transition("FAILED", "CANCELLED") == "CANCELLED"


def test_executing_can_enter_unknown_and_recovery():
    engine = StateTransitionEngine()
    assert engine.transition("EXECUTING", "UNKNOWN") == "UNKNOWN"
    assert engine.transition("UNKNOWN", "RECOVERY_REQUIRED") == "RECOVERY_REQUIRED"
    assert engine.transition("RECOVERY_REQUIRED", "SUCCEEDED") == "SUCCEEDED"


def test_recovery_required_can_redispatch_after_reconcile():
    engine = StateTransitionEngine()
    assert engine.transition("RECOVERY_REQUIRED", "AUTHORIZED") == "AUTHORIZED"
    assert engine.transition("AUTHORIZED", "DISPATCHING") == "DISPATCHING"


def test_terminal_states_accept_no_outgoing_transitions():
    engine = StateTransitionEngine()
    for terminal in ("SUCCEEDED", "REJECTED", "CANCELLED", "MANUAL_INTERVENTION"):
        assert ALLOWED_TRANSITIONS[terminal] == frozenset()


def test_allowed_transitions_table_is_exhaustive():
    assert "RECEIVED" in ALLOWED_TRANSITIONS
    assert "EXECUTING" in ALLOWED_TRANSITIONS
    assert "UNKNOWN" in ALLOWED_TRANSITIONS
    assert "RECOVERY_REQUIRED" in ALLOWED_TRANSITIONS
    assert "FAILED" in ALLOWED_TRANSITIONS
