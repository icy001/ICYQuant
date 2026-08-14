"""Tests for the OrderStatus enum (Commit 33 Part 1.1)."""

from services.order.domain.order_status import OrderStatus


def test_all_statuses_are_defined():
    expected = {
        "CREATED",
        "PENDING_SUBMIT",
        "SUBMITTED",
        "ACCEPTED",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCEL_PENDING",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    }
    assert {status.value for status in OrderStatus} == expected


def test_status_is_a_str_enum():
    assert OrderStatus.CREATED == "CREATED"
    assert OrderStatus.PARTIALLY_FILLED == "PARTIALLY_FILLED"
    assert OrderStatus.CANCEL_PENDING == "CANCEL_PENDING"


def test_status_values_are_strings():
    for status in OrderStatus:
        assert isinstance(status.value, str)


def test_terminal_statuses_exist():
    terminal = {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
    assert OrderStatus.FILLED in terminal
    assert OrderStatus.CANCELLED in terminal
    assert OrderStatus.REJECTED in terminal
    assert OrderStatus.EXPIRED in terminal


def test_from_string_round_trip():
    assert OrderStatus("SUBMITTED") is OrderStatus.SUBMITTED
    assert OrderStatus("PARTIALLY_FILLED") is OrderStatus.PARTIALLY_FILLED
