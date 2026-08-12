"""Tests for ControlContext / ControlRequest (spec sections 7 and 19)."""
from __future__ import annotations

from uuid import uuid4

from services.control_plane.controls.scope import ControlScope
from services.control_plane.gateway.context import (
    ControlContext,
    ControlRequest,
)


def test_context_defaults():
    context = ControlContext()

    assert context.account_id is None
    assert context.portfolio_id is None
    assert context.strategy_id is None
    assert context.symbol is None
    assert context.venue is None
    assert context.order_id is None
    assert context.correlation_id is None


def test_context_holds_order_identity():
    order_id = uuid4()
    context = ControlContext(
        account_id="ACC001",
        strategy_id="alpha_nvda",
        symbol="NVDA",
        venue="NASDAQ",
        order_id=order_id,
    )

    assert context.account_id == "ACC001"
    assert context.strategy_id == "alpha_nvda"
    assert context.symbol == "NVDA"
    assert context.venue == "NASDAQ"
    assert context.order_id == order_id


def test_context_target_maps_scope_to_value():
    context = ControlContext(
        account_id="ACC001",
        portfolio_id="PF-1",
        strategy_id="alpha_nvda",
        symbol="NVDA",
        venue="NASDAQ",
    )

    assert context.target(ControlScope.ACCOUNT) == "ACC001"
    assert context.target(ControlScope.PORTFOLIO) == "PF-1"
    assert context.target(ControlScope.STRATEGY) == "alpha_nvda"
    assert context.target(ControlScope.SYMBOL) == "NVDA"
    assert context.target(ControlScope.VENUE) == "NASDAQ"
    assert context.target(ControlScope.GLOBAL) is None
    assert context.target(ControlScope.ORDER) is None


def test_context_is_frozen():
    import pytest
    from dataclasses import FrozenInstanceError

    context = ControlContext(symbol="NVDA")

    with pytest.raises(FrozenInstanceError):
        context.symbol = "SPY"  # type: ignore[misc]


def test_control_request_defaults():
    request = ControlRequest(context=ControlContext(symbol="NVDA"), action="BUY")

    assert request.context.symbol == "NVDA"
    assert request.action == "BUY"
    assert request.is_new_order is True
    assert request.quantity is None


def test_control_request_carries_quantity():
    request = ControlRequest(
        context=ControlContext(symbol="NVDA"),
        action="SELL_CLOSE",
        is_new_order=False,
        quantity=100.0,
    )

    assert request.is_new_order is False
    assert request.quantity == 100.0
