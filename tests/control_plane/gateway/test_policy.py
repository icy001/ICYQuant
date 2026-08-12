"""Tests for GatewayPolicy and CONTROL_PRIORITY (spec sections 10 and 15)."""
from __future__ import annotations

from services.control_plane.controls.control_type import ControlType
from services.control_plane.gateway.policy import (
    CONTROL_PRIORITY,
    GatewayPolicy,
)
from services.control_plane.gateway.state import GatewayState


def test_default_policy_is_fail_closed():
    policy = GatewayPolicy()

    assert policy.fail_safe_state is GatewayState.FAIL_SAFE
    assert policy.fail_open is False
    assert policy.require_control_registry is True


def test_policy_can_be_customised():
    policy = GatewayPolicy(
        fail_safe_state=GatewayState.DISABLED,
        fail_open=True,
        require_control_registry=False,
    )

    assert policy.fail_safe_state is GatewayState.DISABLED
    assert policy.fail_open is True
    assert policy.require_control_registry is False


def test_control_priority_orders_blocking_controls():
    assert CONTROL_PRIORITY[ControlType.KILL_SWITCH] > CONTROL_PRIORITY[ControlType.DISABLE_EXECUTION]
    assert CONTROL_PRIORITY[ControlType.DISABLE_EXECUTION] > CONTROL_PRIORITY[ControlType.BLOCK_NEW_ORDERS]
    assert CONTROL_PRIORITY[ControlType.BLOCK_NEW_ORDERS] > CONTROL_PRIORITY[ControlType.DISABLE_STRATEGY]
    assert CONTROL_PRIORITY[ControlType.DISABLE_STRATEGY] > CONTROL_PRIORITY[ControlType.REDUCE_ONLY]
    assert CONTROL_PRIORITY[ControlType.REDUCE_ONLY] > CONTROL_PRIORITY[ControlType.PAUSE_STRATEGY]
    assert CONTROL_PRIORITY[ControlType.PAUSE_STRATEGY] > CONTROL_PRIORITY[ControlType.NORMAL]


def test_control_priority_absolute_levels():
    # BLOCK > REDUCE_ONLY > ALLOW (spec section 15).
    assert CONTROL_PRIORITY[ControlType.KILL_SWITCH] == 1000
    assert CONTROL_PRIORITY[ControlType.DISABLE_EXECUTION] == 900
    assert CONTROL_PRIORITY[ControlType.BLOCK_NEW_ORDERS] == 800
    assert CONTROL_PRIORITY[ControlType.DISABLE_STRATEGY] == 700
    assert CONTROL_PRIORITY[ControlType.REDUCE_ONLY] == 600
    assert CONTROL_PRIORITY[ControlType.PAUSE_STRATEGY] == 500
    assert CONTROL_PRIORITY[ControlType.NORMAL] == 0
