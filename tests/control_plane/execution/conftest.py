"""Shared fixtures for the Execution Control test suite."""

import pytest

from services.control_plane.execution import (
    ExecutionController,
    ExecutionControlPolicy,
)


@pytest.fixture
def controller() -> ExecutionController:
    """A fresh ExecutionController with the default policy."""
    return ExecutionController()


@pytest.fixture
def strict_controller() -> ExecutionController:
    """An ExecutionController whose non-active states close the risk-reduction
    channels too."""
    return ExecutionController(
        policy=ExecutionControlPolicy(
            degraded_allow_new=False,
            paused_allow_cancel=False,
            paused_allow_reduce=False,
            draining_allow_cancel=False,
            draining_allow_reduce=False,
            disabled_allow_cancel=False,
            disabled_allow_emergency_flatten=False,
        ),
    )
