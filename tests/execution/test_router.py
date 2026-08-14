import pytest

from services.execution.application.router import (
    ExecutionRouter,
    NoExecutionVenueAvailable,
)
from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionSide,
)
from services.execution.domain.routing import (
    ExecutionRoutingPolicy,
)
from services.execution.domain.venue import (
    ExecutionVenue,
    ExecutionVenueType,
)


def build_request():
    return ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.MARKET,
        quantity=100,
    )


def test_preferred_venue_is_selected():

    router = ExecutionRouter(
        {
            "sim": ExecutionVenue(
                venue_id="sim",
                name="Simulator",
                venue_type=(
                    ExecutionVenueType.SIMULATOR
                ),
            ),
            "broker": ExecutionVenue(
                venue_id="broker",
                name="Broker",
                venue_type=(
                    ExecutionVenueType.BROKER
                ),
            ),
        }
    )

    policy = ExecutionRoutingPolicy(
        preferred_venue="broker",
        allowed_venues=(
            "broker",
            "sim",
        ),
    )

    result = router.route(
        build_request(),
        policy,
    )

    assert result.venue.venue_id == "broker"


def test_disabled_venue_is_skipped():

    router = ExecutionRouter(
        {
            "broker": ExecutionVenue(
                venue_id="broker",
                name="Broker",
                venue_type=(
                    ExecutionVenueType.BROKER
                ),
                enabled=False,
            ),
            "sim": ExecutionVenue(
                venue_id="sim",
                name="Simulator",
                venue_type=(
                    ExecutionVenueType.SIMULATOR
                ),
            ),
        }
    )

    policy = ExecutionRoutingPolicy(
        preferred_venue="broker",
        fallback_venues=("sim",),
    )

    result = router.route(
        build_request(),
        policy,
    )

    assert result.venue.venue_id == "sim"


def test_no_available_venue():

    router = ExecutionRouter({})

    policy = ExecutionRoutingPolicy(
        allowed_venues=("broker",)
    )

    with pytest.raises(
        NoExecutionVenueAvailable
    ):
        router.route(
            build_request(),
            policy,
        )
