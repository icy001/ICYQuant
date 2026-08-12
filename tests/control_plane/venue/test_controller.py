"""Tests for VenueController (Commit 26 Part 1.4, spec sections 11–12, 22–23, 30)."""

from uuid import uuid4

from services.control_plane.venue import VenueState
from services.control_plane.venue.audit import (
    VenueControlAuditEventType,
)


def test_default_state_is_online(controller):
    assert controller.state("NASDAQ") is VenueState.ONLINE


def test_online_venue_has_full_capability(controller):
    decision = controller.evaluate("NASDAQ")
    assert decision.venue == "NASDAQ"
    assert decision.state is VenueState.ONLINE
    assert decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "venue_online"


def test_degraded_venue_blocks_new_orders_by_default(controller):
    controller.set_state("NASDAQ", VenueState.DEGRADED)

    decision = controller.evaluate("NASDAQ")

    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.reason == "venue_degraded"


def test_degraded_venue_can_allow_new_via_policy(controller):
    from services.control_plane.venue import VenueControlPolicy

    flexible = controller.__class__(
        policy=VenueControlPolicy(degraded_allow_new=True),
    )
    flexible.set_state("NASDAQ", VenueState.DEGRADED)

    decision = flexible.evaluate("NASDAQ")

    assert decision.allow_new_orders


def test_paused_venue_allows_cancel(controller):
    controller.set_state("NASDAQ", VenueState.PAUSED)

    decision = controller.evaluate("NASDAQ")

    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "venue_paused"


def test_disabled_venue_preserves_emergency_flatten(controller):
    controller.set_state("NASDAQ", VenueState.DISABLED)

    decision = controller.evaluate("NASDAQ")

    assert not decision.allow_new_orders
    assert decision.allow_cancel_orders
    assert not decision.allow_reduce_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "venue_disabled"


def test_disabled_venue_preserves_cancel_and_flatten_regardless_of_policy(
    strict_controller,
):
    """spec §11：DISABLED 分支的 Cancel / Flatten 是硬编码保留的，
    不受 policy.disabled_allow_cancel / disabled_allow_emergency_flatten 影响。"""
    strict_controller.set_state("NASDAQ", VenueState.DISABLED)

    decision = strict_controller.evaluate("NASDAQ")

    assert decision.allow_cancel_orders
    assert decision.allow_emergency_flatten


def test_failover_venue_blocks_new_but_keeps_cancel_flatten(controller):
    controller.set_state("NASDAQ", VenueState.FAILOVER)

    decision = controller.evaluate("NASDAQ")

    assert not decision.allow_new_orders
    assert not decision.allow_reduce_orders
    assert decision.allow_cancel_orders
    assert decision.allow_emergency_flatten
    assert decision.reason == "venue_failover"


def test_unknown_venue_is_fail_closed(controller):
    controller.set_state("NASDAQ", VenueState.UNKNOWN)

    decision = controller.evaluate("NASDAQ")

    assert not decision.allow_new_orders
    assert not decision.allow_cancel_orders
    assert not decision.allow_reduce_orders
    assert not decision.allow_emergency_flatten
    assert decision.reason == "venue_unknown"


def test_disabled_venue_does_not_disable_other_venues(controller):
    controller.set_state("NASDAQ", VenueState.DISABLED)

    nasdaq = controller.evaluate("NASDAQ")
    nyse = controller.evaluate("NYSE")

    assert not nasdaq.allow_new_orders
    assert nyse.allow_new_orders


def test_state_transition_emits_audit_event(controller):
    controller.set_state(
        "NASDAQ",
        VenueState.DEGRADED,
        incident_id=uuid4(),
        control_id=uuid4(),
        execution_id="exec_north",
        actor="health-monitor",
        reason="order reject rate 35%",
    )

    records = controller.audit_trail
    assert len(records) == 1
    record = records[0]
    assert record.event_type is (
        VenueControlAuditEventType.VENUE_DEGRADED
    )
    assert record.venue == "NASDAQ"
    assert record.previous_state is VenueState.ONLINE
    assert record.new_state is VenueState.DEGRADED
    assert record.execution_id == "exec_north"
    assert record.actor == "health-monitor"
    assert record.reason == "order reject rate 35%"
    assert record.incident_id is not None
    assert record.control_id is not None


def test_failover_lifecycle_audit_events(controller):
    controller.set_state("NASDAQ", VenueState.FAILOVER)
    controller.set_state("NASDAQ", VenueState.ONLINE)

    assert [
        r.event_type for r in controller.audit_trail
    ] == [
        VenueControlAuditEventType.VENUE_FAILOVER_STARTED,
        VenueControlAuditEventType.VENUE_FAILOVER_COMPLETED,
    ]


def test_recovered_audit_event(controller):
    controller.set_state("NASDAQ", VenueState.PAUSED)
    controller.set_state("NASDAQ", VenueState.ONLINE)

    assert (
        controller.audit_trail[-1].event_type
        is VenueControlAuditEventType.VENUE_RECOVERED
    )


def test_duplicate_state_change_does_not_emit_audit_event(controller):
    controller.set_state("NASDAQ", VenueState.DISABLED)
    controller.set_state("NASDAQ", VenueState.DISABLED)

    assert len(controller.audit_trail) == 1
