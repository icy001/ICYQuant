"""Shared fixtures for the Routing Control test suite."""

import pytest

from services.control_plane.routing import (
    RoutingController,
    RoutingPolicy,
)
from services.control_plane.venue import VenueController


@pytest.fixture
def venue_controller() -> VenueController:
    """A fresh VenueController shared with the router."""
    return VenueController()


@pytest.fixture
def router(venue_controller) -> RoutingController:
    """A RoutingController backed by the shared VenueController."""
    return RoutingController(
        venue_controller=venue_controller,
        policy=RoutingPolicy(),
    )
