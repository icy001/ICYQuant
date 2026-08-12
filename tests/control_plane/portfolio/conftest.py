"""Shared fixtures for the Portfolio Control test suite."""

import pytest

from services.control_plane.portfolio import (
    PortfolioController,
    PortfolioControlPolicy,
)


@pytest.fixture
def controller() -> PortfolioController:
    """A fresh PortfolioController with the default policy."""
    return PortfolioController()


@pytest.fixture
def strict_controller() -> PortfolioController:
    """A PortfolioController whose restricted state blocks reductions too."""
    return PortfolioController(
        policy=PortfolioControlPolicy(
            restricted_allow_reduce=False,
            reduce_only_allow_reduce=False,
            frozen_allow_reduce=False,
            liquidating_allow_reduce=False,
        ),
    )
