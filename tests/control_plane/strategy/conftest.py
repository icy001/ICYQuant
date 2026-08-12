"""Shared fixtures for the Strategy Control test suite."""

import pytest

from services.control_plane.strategy import (
    StrategyController,
    StrategyControlPolicy,
)


@pytest.fixture
def controller() -> StrategyController:
    """A fresh StrategyController with the default policy."""
    return StrategyController()


@pytest.fixture
def strict_controller() -> StrategyController:
    """A StrategyController whose non-running states block reductions too."""
    return StrategyController(
        policy=StrategyControlPolicy(
            paused_allow_reduce=False,
            draining_allow_reduce=False,
            disabled_allow_reduce=False,
            disabled_allow_signal=True,
        ),
    )
