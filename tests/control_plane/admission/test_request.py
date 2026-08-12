"""Tests for OrderAdmissionRequest (spec section 3)."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.control_plane.admission.request import OrderAdmissionRequest
from services.control_plane.gateway.context import ControlContext


def _request(**kwargs):
    defaults = {
        "context": ControlContext(symbol="NVDA"),
        "symbol": "NVDA",
        "side": "BUY",
        "quantity": 100,
        "order_type": "LIMIT",
    }
    defaults.update(kwargs)
    return OrderAdmissionRequest(**defaults)


def test_request_defaults():
    req = _request()

    assert req.symbol == "NVDA"
    assert req.side == "BUY"
    assert req.quantity == 100
    assert req.order_type == "LIMIT"
    assert req.is_reduce_only is False
    assert req.metadata == {}
    assert req.request_id is not None
    assert req.created_at.tzinfo is not None


def test_request_id_is_unique():
    assert _request().request_id != _request().request_id


def test_request_carries_context():
    context = ControlContext(
        account_id="ACC001",
        strategy_id="alpha_nvda",
        symbol="NVDA",
        venue="NASDAQ",
    )
    req = _request(context=context)

    assert req.context.account_id == "ACC001"
    assert req.context.strategy_id == "alpha_nvda"
    assert req.context.symbol == "NVDA"


def test_request_carries_metadata():
    req = _request(metadata={"client_id": "portfolio-1"})

    assert req.metadata == {"client_id": "portfolio-1"}


def test_request_is_frozen():
    req = _request()

    with pytest.raises(FrozenInstanceError):
        req.quantity = 200  # type: ignore[misc]


def test_reduce_only_flag():
    assert _request(is_reduce_only=True).is_reduce_only is True
