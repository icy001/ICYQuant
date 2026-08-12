"""
Tests for GlobalControlController (Commit 26 Part 1.5,
spec sections 6, 25-26, 30-31).
"""

from uuid import uuid4

from services.control_plane.global_control import GlobalControlState
from services.control_plane.global_control.audit import (
    GlobalControlAuditEventType,
)


def test_default_state_is_normal(controller):
    assert controller.state is GlobalControlState.NORMAL


def test_normal_state_allows_everything(controller):
    decision = controller.evaluate()

    assert decision.state is GlobalControlState.NORMAL
    assert decision.allow_new_risk
    assert decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert not decision.allow_recovery
    assert decision.reason == "global_normal"


def test_restricted_state_blocks_new_risk(controller):
    controller.set_state(GlobalControlState.RESTRICTED)

    decision = controller.evaluate()

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert not decision.allow_recovery
    assert decision.reason == "global_restricted"


def test_global_kill_blocks_new_orders(controller):
    controller.set_state(GlobalControlState.KILLED)

    decision = controller.evaluate()

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert decision.allow_recovery
    assert decision.reason == "global_killed"


def test_global_kill_preserves_risk_reduction(controller):
    controller.set_state(GlobalControlState.KILLED)

    decision = controller.evaluate()

    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten


def test_global_kill_can_block_risk_reduction_via_policy(strict_controller):
    strict_controller.set_state(GlobalControlState.KILLED)

    decision = strict_controller.evaluate()

    assert not decision.allow_cancel_orders
    assert not decision.allow_reduce_orders
    assert not decision.allow_emergency_flatten


def test_recovery_state_keeps_risk_reduction(controller):
    controller.set_state(GlobalControlState.RECOVERY)

    decision = controller.evaluate()

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert decision.allow_recovery
    assert decision.reason == "global_recovery"


def test_duplicate_state_change_does_not_emit_audit_event(controller):
    controller.set_state(GlobalControlState.KILLED)
    controller.set_state(GlobalControlState.KILLED)

    assert len(controller.audit_trail) == 1


def test_kill_transition_emits_audit_event(controller):
    controller.set_state(
        GlobalControlState.KILLED,
        incident_id=uuid4(),
        control_id=uuid4(),
        actor="incident-responder",
        reason="market disruption",
        system_state="flattened",
    )

    records = controller.audit_trail
    assert len(records) == 1
    record = records[0]
    assert record.event_type is (
        GlobalControlAuditEventType.GLOBAL_KILL_ACTIVATED
    )
    assert record.previous_state is GlobalControlState.NORMAL
    assert record.new_state is GlobalControlState.KILLED
    assert record.actor == "incident-responder"
    assert record.reason == "market disruption"
    assert record.system_state == "flattened"
    assert record.incident_id is not None
    assert record.control_id is not None


def test_restriction_emits_audit_event(controller):
    controller.set_state(GlobalControlState.RESTRICTED)

    assert (
        controller.audit_trail[-1].event_type
        is GlobalControlAuditEventType.GLOBAL_RESTRICTION_ENABLED
    )


def test_recovery_entry_emits_audit_event(controller):
    controller.set_state(GlobalControlState.KILLED)
    controller.set_state(GlobalControlState.RECOVERY)

    assert (
        controller.audit_trail[-1].event_type
        is GlobalControlAuditEventType.RECOVERY_STARTED
    )


def test_recovery_completion_emits_audit_event(controller):
    controller.set_state(GlobalControlState.RECOVERY)
    controller.set_state(GlobalControlState.NORMAL)

    assert (
        controller.audit_trail[-1].event_type
        is GlobalControlAuditEventType.RECOVERY_COMPLETED
    )
