"""Tests for GatewayState (spec section 9)."""
from __future__ import annotations

from services.control_plane.gateway.state import GatewayState


def test_state_values():
    assert GatewayState.HEALTHY.value == "HEALTHY"
    assert GatewayState.DEGRADED.value == "DEGRADED"
    assert GatewayState.FAIL_SAFE.value == "FAIL_SAFE"
    assert GatewayState.DISABLED.value == "DISABLED"


def test_fail_safe_and_disabled_block_new_orders():
    assert GatewayState.FAIL_SAFE.blocks_new_orders is True
    assert GatewayState.DISABLED.blocks_new_orders is True


def test_healthy_and_degraded_do_not_block_new_orders():
    assert GatewayState.HEALTHY.blocks_new_orders is False
    assert GatewayState.DEGRADED.blocks_new_orders is False


def test_state_round_trip():
    assert GatewayState("FAIL_SAFE") is GatewayState.FAIL_SAFE
