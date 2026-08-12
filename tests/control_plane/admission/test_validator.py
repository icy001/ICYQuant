"""Tests for OrderAdmissionValidator (spec section 6)."""
from __future__ import annotations

import pytest

from services.control_plane.admission.request import OrderAdmissionRequest
from services.control_plane.admission.validator import (
    OrderAdmissionValidator,
)
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


def test_valid_request_passes():
    OrderAdmissionValidator().validate(_request())


def test_symbol_required():
    with pytest.raises(ValueError, match="symbol is required"):
        OrderAdmissionValidator().validate(_request(symbol=""))


def test_side_required():
    with pytest.raises(ValueError, match="side is required"):
        OrderAdmissionValidator().validate(_request(side=""))


def test_order_type_required():
    with pytest.raises(ValueError, match="order_type is required"):
        OrderAdmissionValidator().validate(_request(order_type=""))


def test_zero_quantity_rejected():
    with pytest.raises(ValueError, match="quantity must be positive"):
        OrderAdmissionValidator().validate(_request(quantity=0))


def test_negative_quantity_rejected():
    with pytest.raises(ValueError, match="quantity must be positive"):
        OrderAdmissionValidator().validate(_request(quantity=-10))
