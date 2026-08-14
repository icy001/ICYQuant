"""Tests for the OrderType enum (Commit 33 Part 1.1)."""

from services.order.domain.order_type import OrderType


def test_core_types_are_defined():
    assert {order_type.value for order_type in OrderType} == {"MARKET", "LIMIT"}


def test_order_type_is_a_str_enum():
    assert OrderType.MARKET == "MARKET"
    assert OrderType.LIMIT == "LIMIT"


def test_from_string_round_trip():
    assert OrderType("MARKET") is OrderType.MARKET
    assert OrderType("LIMIT") is OrderType.LIMIT


def test_no_stop_types_yet():
    # STOP / STOP_LIMIT / TRAILING_STOP are reserved for later parts.
    assert OrderType.MARKET.value not in {"STOP", "STOP_LIMIT", "TRAILING_STOP"}
    assert len(list(OrderType)) == 2
