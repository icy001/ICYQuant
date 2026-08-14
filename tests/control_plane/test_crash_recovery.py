"""Crash recovery boundary (§24-26, §38)."""

from __future__ import annotations

import pytest

from services.control_plane.recovery_engine import ControlRecovery, RecoveryAction
from services.control_plane.store import InMemoryCommandStore


def test_executing_after_crash_is_recovery_required(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="EXECUTING", version=7))
    decision = ControlRecovery().recover_after_crash(store, "CMD-001")
    assert decision.action == RecoveryAction.RECONCILE.value
    assert decision.state == "RECOVERY_REQUIRED"


def test_unknown_after_crash_is_recovery_required(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="UNKNOWN", version=7))
    decision = ControlRecovery().recover_after_crash(store, "CMD-001")
    assert decision.action == RecoveryAction.RECONCILE.value
    assert decision.state == "RECOVERY_REQUIRED"


@pytest.mark.parametrize("state", ["RECEIVED", "AUTHORIZING", "AUTHORIZED", "DISPATCHING"])
def test_pre_execution_crash_is_safe_to_restart(make_record, state):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state=state, version=7))
    decision = ControlRecovery().recover_after_crash(store, "CMD-001")
    assert decision.action == RecoveryAction.RESTART.value
    assert decision.state == "AUTHORIZED"


@pytest.mark.parametrize("state", ["SUCCEEDED", "FAILED", "REJECTED", "CANCELLED"])
def test_terminal_state_needs_no_recovery(make_record, state):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state=state, version=7))
    decision = ControlRecovery().recover_after_crash(store, "CMD-001")
    assert decision.action == RecoveryAction.NO_ACTION.value
    assert decision.state == state


def test_crash_never_auto_marks_failed(make_record):
    """§24: EXECUTING after a crash is never downgraded to FAILED."""
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="EXECUTING", version=7))
    decision = ControlRecovery().recover_after_crash(store, "CMD-001")
    assert decision.state != "FAILED"
