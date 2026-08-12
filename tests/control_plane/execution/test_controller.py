"""Tests for ExecutionController (Commit 26 Part 1.4, spec sections 6, 22–23)."""

from uuid import uuid4

from services.control_plane.execution import ExecutionState
from services.control_plane.execution.audit import (
    ExecutionControlAuditEventType,
)


def test_default_state_is_active(controller):
    assert controller.state("exec_north") is ExecutionState.ACTIVE


def test_active_execution_has_full_capability(controller):
    decision = controller.evaluate("exec_north")
    assert decision.execution_id == "exec_north"
    assert decision.state is ExecutionState.ACTIVE
    assert decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "execution_active"


def test_degraded_execution_allows_new_by_default(controller):
    controller.set_state("exec_north", ExecutionState.DEGRADED)

    decision = controller.evaluate("exec_north")

    assert decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.reason == "execution_degraded"


def test_degraded_execution_blocks_new_when_policy_forbids(strict_controller):
    strict_controller.set_state("exec_north", ExecutionState.DEGRADED)

    decision = strict_controller.evaluate("exec_north")

    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders


def test_paused_execution_blocks_new_but_keeps_risk_reduction(controller):
    controller.set_state("exec_north", ExecutionState.PAUSED)

    decision = controller.evaluate("exec_north")

    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "execution_paused"


def test_draining_execution_blocks_new_but_keeps_cancel_reduce(controller):
    controller.set_state("exec_north", ExecutionState.DRAINING)

    decision = controller.evaluate("exec_north")

    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.reason == "execution_draining"


def test_disabled_execution_blocks_new_and_reduce_but_keeps_cancel(controller):
    controller.set_state("exec_north", ExecutionState.DISABLED)

    decision = controller.evaluate("exec_north")

    assert not decision.allow_new_orders
    assert not decision.allow_reduce_orders
    assert decision.allow_cancel_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "execution_disabled"


def test_disabled_execution_can_close_cancel_channel(strict_controller):
    strict_controller.set_state("exec_north", ExecutionState.DISABLED)

    decision = strict_controller.evaluate("exec_north")

    assert not decision.allow_cancel_orders
    assert not decision.allow_emergency_flatten


def test_failover_execution_blocks_new_but_keeps_cancel_flatten(controller):
    controller.set_state("exec_north", ExecutionState.FAILOVER)

    decision = controller.evaluate("exec_north")

    assert not decision.allow_new_orders
    assert not decision.allow_reduce_orders
    assert decision.allow_cancel_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "execution_failover"


def test_execution_control_isolated(controller):
    """Pausing exec_north must not affect exec_south."""
    controller.set_state("exec_north", ExecutionState.PAUSED)

    north = controller.evaluate("exec_north")
    south = controller.evaluate("exec_south")

    assert not north.allow_new_orders
    assert south.allow_new_orders


def test_state_transition_emits_audit_event(controller):
    controller.set_state(
        "exec_north",
        ExecutionState.PAUSED,
        incident_id=uuid4(),
        control_id=uuid4(),
        venue="NASDAQ",
        actor="risk-operator",
        reason="venue latency critical",
    )

    records = controller.audit_trail
    assert len(records) == 1
    record = records[0]
    assert record.event_type is (
        ExecutionControlAuditEventType.EXECUTION_PAUSED
    )
    assert record.execution_id == "exec_north"
    assert record.previous_state is ExecutionState.ACTIVE
    assert record.new_state is ExecutionState.PAUSED
    assert record.venue == "NASDAQ"
    assert record.actor == "risk-operator"
    assert record.reason == "venue latency critical"
    assert record.incident_id is not None
    assert record.control_id is not None


def test_audit_event_mapping_for_each_state(controller):
    expected = {
        ExecutionState.ACTIVE: (
            ExecutionControlAuditEventType.EXECUTION_ACTIVE
        ),
        ExecutionState.DEGRADED: (
            ExecutionControlAuditEventType.EXECUTION_DEGRADED
        ),
        ExecutionState.PAUSED: (
            ExecutionControlAuditEventType.EXECUTION_PAUSED
        ),
        ExecutionState.DRAINING: (
            ExecutionControlAuditEventType.EXECUTION_DRAINING
        ),
        ExecutionState.DISABLED: (
            ExecutionControlAuditEventType.EXECUTION_DISABLED
        ),
        ExecutionState.FAILOVER: (
            ExecutionControlAuditEventType.EXECUTION_FAILOVER
        ),
    }
    # Leave the default ACTIVE state first so every transition below fires.
    controller.set_state("exec_north", ExecutionState.PAUSED)

    for state, event_type in expected.items():
        controller.set_state("exec_north", state)
        assert controller.audit_trail[-1].event_type is event_type


def test_duplicate_state_change_does_not_emit_audit_event(controller):
    controller.set_state("exec_north", ExecutionState.PAUSED)
    controller.set_state("exec_north", ExecutionState.PAUSED)

    assert len(controller.audit_trail) == 1
