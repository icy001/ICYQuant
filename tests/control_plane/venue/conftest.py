"""Shared fixtures for the Venue Control test suite."""

import pytest

from services.control_plane.venue import (
    VenueController,
    VenueControlPolicy,
)


@pytest.fixture
def controller() -> VenueController:
    """A fresh VenueController with the default policy."""
    return VenueController()


@pytest.fixture
def strict_controller() -> VenueController:
    """A VenueController with a strict policy.

    spec §11：即使 policy 尝试关闭 cancel / flatten，DISABLED 分支仍
    硬编码保留 Cancel 与 Flatten；reduce 则由 policy 控制。
    """
    return VenueController(
        policy=VenueControlPolicy(
            disabled_allow_cancel=False,
            disabled_allow_reduce=False,
            disabled_allow_emergency_flatten=False,
        ),
    )
