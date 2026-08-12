"""Tests for ExecutionControlService
(Commit 26 Part 1.4, spec sections 20, 26).

A new order may reach execution only if Execution AND Venue AND Routing all
allow it — while cancel / reduce / emergency flatten follow the independent
risk-reduction path.
"""

import pytest

from services.control_plane.execution import (
    ExecutionControlRequest,
    ExecutionControlService,
    ExecutionController,
    ExecutionControlPolicy,
    ExecutionState,
    ExecutionVerdict,
)
from services.control_plane.routing import RoutingController
from services.control_plane.venue import (
    VenueController,
    VenueState,
)


@pytest.fixture
def service():
    venue_controller = VenueController()
    return ExecutionControlService(
        execution_controller=ExecutionController(),
        venue_controller=venue_controller,
        routing_controller=RoutingController(
            venue_controller=venue_controller,
        ),
    )


@pytest.fixture
def strict_service():
    """An ExecutionControlService whose disabled execution also blocks cancels."""
    venue_controller = VenueController()
    return ExecutionControlService(
        execution_controller=ExecutionController(
            policy=ExecutionControlPolicy(
                disabled_allow_cancel=False,
            ),
        ),
        venue_controller=venue_controller,
        routing_controller=RoutingController(
            venue_controller=venue_controller,
        ),
    )


def _request(
    venue="NASDAQ",
    action="NEW_ORDER",
    **kwargs,
) -> ExecutionControlRequest:
    return ExecutionControlRequest(
        execution_id="exec_north",
        venue=venue,
        action=action,
        **kwargs,
    )


def test_new_order_allowed_when_everything_active(service):
    result = service.authorize(_request())

    assert result.verdict is ExecutionVerdict.ALLOW
    assert result.allowed


def test_new_order_blocked_when_venue_disabled(service):
    service.venue_controller.set_state("NASDAQ", VenueState.DISABLED)

    result = service.authorize(_request())

    assert result.verdict is ExecutionVerdict.BLOCK
    assert not result.allowed
    assert result.reason == "no_available_venue"


def test_new_order_redirected_to_fallback_venue(service):
    service.venue_controller.set_state("NASDAQ", VenueState.FAILOVER)

    result = service.authorize(
        _request(),
        fallback_venues=["NYSE"],
    )

    assert result.verdict is ExecutionVerdict.REDIRECT
    assert result.allowed
    assert result.routing_decision is not None
    assert result.routing_decision.selected_venue == "NYSE"
    assert result.routing_decision.fallback_venue is None


def test_cancel_allowed_on_paused_venue(service):
    service.venue_controller.set_state("NASDAQ", VenueState.PAUSED)

    result = service.authorize(
        _request(action="CANCEL_ORDER"),
    )

    assert result.verdict is ExecutionVerdict.CANCEL_ALLOWED
    assert result.allowed


def test_cancel_blocked_when_execution_disabled(strict_service):
    strict_service.execution_controller.set_state(
        "exec_north",
        ExecutionState.DISABLED,
    )

    result = strict_service.authorize(
        _request(action="CANCEL_ORDER"),
    )

    assert result.verdict is ExecutionVerdict.BLOCK


def test_reduce_allowed_on_reduce_only_request(service):
    result = service.authorize(
        _request(reduce_only=True),
    )

    assert result.verdict is ExecutionVerdict.REDUCE_ONLY
    assert result.allowed


def test_reduce_blocked_when_venue_failover(service):
    service.venue_controller.set_state("NASDAQ", VenueState.FAILOVER)

    result = service.authorize(
        _request(action="REDUCE_ORDER"),
    )

    assert result.verdict is ExecutionVerdict.BLOCK
    assert not result.allowed


def test_emergency_flatten_allowed_on_disabled_venue(service):
    """Emergency flatten survives a disabled venue (spec section 23)."""
    service.venue_controller.set_state("NASDAQ", VenueState.DISABLED)

    result = service.authorize(
        _request(action="EMERGENCY_FLATTEN"),
    )

    assert result.verdict is ExecutionVerdict.ALLOW
    assert result.allowed


def test_emergency_flatten_routed_to_backup_venue(service):
    service.venue_controller.set_state("NASDAQ", VenueState.DISABLED)

    result = service.authorize(
        _request(action="EMERGENCY_FLATTEN"),
        fallback_venues=["NYSE"],
    )

    assert result.verdict is ExecutionVerdict.EMERGENCY_ROUTE
    assert result.allowed
    assert result.routing_decision is not None
    assert result.routing_decision.selected_venue == "NYSE"


def test_emergency_flatten_blocked_when_no_venue_available(service):
    service.venue_controller.set_state("NASDAQ", VenueState.DISABLED)
    service.venue_controller.set_state("NYSE", VenueState.DISABLED)

    result = service.authorize(
        _request(action="EMERGENCY_FLATTEN"),
        fallback_venues=["NYSE"],
    )

    assert result.verdict is ExecutionVerdict.BLOCK
    assert not result.allowed
    assert result.reason == "no_available_venue"
