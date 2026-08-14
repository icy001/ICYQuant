"""Tests for the OrderSide enum (Commit 33 Part 1.1)."""

from services.order.domain.order_side import OrderSide


def test_only_buy_and_sell():
    assert {side.value for side in OrderSide} == {"BUY", "SELL"}


def test_order_side_is_a_str_enum():
    assert OrderSide.BUY == "BUY"
    assert OrderSide.SELL == "SELL"


def test_long_short_are_not_order_sides():
    # LONG / SHORT are position / exposure semantics, not order direction.
    assert not hasattr(OrderSide, "LONG")
    assert not hasattr(OrderSide, "SHORT")


def test_from_string_round_trip():
    assert OrderSide("BUY") is OrderSide.BUY
    assert OrderSide("SELL") is OrderSide.SELL
