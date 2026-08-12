"""Shared fixtures for the Global Control test suite."""

import pytest

from services.control_plane.global_control import (
    GlobalControlController,
    GlobalControlPolicy,
    GlobalKillSwitch,
)


@pytest.fixture
def controller() -> GlobalControlController:
    """A fresh GlobalControlController with the default policy."""
    return GlobalControlController()


@pytest.fixture
def strict_controller() -> GlobalControlController:
    """A GlobalControlController whose KILLED state also blocks risk reduction.

    注意：与 Venue DISABLED 不同，Global KILLED 的 Cancel / Reduce / Flatten
    是由 policy 配置的（spec section 5），因此可以被关闭。
    """
    return GlobalControlController(
        policy=GlobalControlPolicy(
            killed_allow_cancel=False,
            killed_allow_reduce=False,
            killed_allow_emergency_flatten=False,
        ),
    )


@pytest.fixture
def kill_switch(controller) -> GlobalKillSwitch:
    """A GlobalKillSwitch bound to the default controller."""
    return GlobalKillSwitch(controller)
