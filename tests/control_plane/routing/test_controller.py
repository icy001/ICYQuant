"""Tests for RoutingController (Commit 26 Part 1.4, spec sections 15–16, 30)."""

from uuid import uuid4

from services.control_plane.venue import VenueState
from services.control_plane.routing.audit import (
    RoutingAuditEventType,
)


def test_router_selects_first_healthy_venue(router, venue_controller):
    decision = router.select(["NASDAQ", "NYSE"])

    assert decision.allowed
    assert decision.selected_venue == "NASDAQ"
    assert decision.fallback_venue == "NYSE"
    assert decision.reason == "venue_available"


def test_router_selects_healthy_fallback(router, venue_controller):
    venue_controller.set_state("NASDAQ", VenueState.FAILOVER)

    decision = router.select(["NASDAQ", "NYSE"])

    assert decision.allowed
    assert decision.selected_venue == "NYSE"
    assert decision.fallback_venue is None


def test_router_blocks_when_no_venue_available(router, venue_controller):
    venue_controller.set_state("NASDAQ", VenueState.DISABLED)
    venue_controller.set_state("NYSE", VenueState.DISABLED)

    decision = router.select(["NASDAQ", "NYSE"])

    assert not decision.allowed
    assert decision.selected_venue is None
    assert decision.fallback_venue is None
    assert decision.reason == "no_available_venue"


def test_router_skips_degraded_venue_by_default(router, venue_controller):
    venue_controller.set_state("NASDAQ", VenueState.DEGRADED)

    decision = router.select(["NASDAQ", "NYSE"])

    assert decision.allowed
    assert decision.selected_venue == "NYSE"


def test_router_ignores_duplicate_venues(router, venue_controller):
    venue_controller.set_state("NASDAQ", VenueState.DISABLED)

    decision = router.select(["NASDAQ", "NYSE"])

    assert decision.allowed
    assert decision.selected_venue == "NYSE"


def test_route_allowed_is_audited(router, venue_controller):
    router.select(["NASDAQ", "NYSE"])

    records = router.audit_trail
    assert len(records) == 1
    assert records[0].event_type is RoutingAuditEventType.ROUTE_ALLOWED
    assert records[0].selected_venue == "NASDAQ"
    assert records[0].fallback_venue == "NYSE"


def test_route_redirected_is_audited(router, venue_controller):
    venue_controller.set_state("NASDAQ", VenueState.FAILOVER)

    router.select(
        ["NASDAQ", "NYSE"],
        incident_id=uuid4(),
        control_id=uuid4(),
        execution_id="exec_north",
        actor="risk-operator",
    )

    records = router.audit_trail
    assert len(records) == 1
    record = records[0]
    assert record.event_type is RoutingAuditEventType.ROUTE_REDIRECTED
    assert record.selected_venue == "NYSE"
    assert record.venues == ("NASDAQ", "NYSE")
    assert record.execution_id == "exec_north"
    assert record.actor == "risk-operator"
    assert record.incident_id is not None
    assert record.control_id is not None


def test_route_blocked_is_audited(router, venue_controller):
    venue_controller.set_state("NASDAQ", VenueState.DISABLED)

    router.select(["NASDAQ"])

    records = router.audit_trail
    assert len(records) == 1
    assert records[0].event_type is RoutingAuditEventType.ROUTE_BLOCKED
    assert records[0].selected_venue is None


def test_audit_trail_is_immutable_view(router, venue_controller):
    router.select(["NASDAQ"])
    snapshot = router.audit_trail
    router.select(["NASDAQ", "NYSE"])

    assert len(snapshot) == 1
    assert len(router.audit_trail) == 2
