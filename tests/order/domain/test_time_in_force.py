"""Tests for the TimeInForce enum (Commit 33 Part 1.1)."""

from services.order.domain.time_in_force import TimeInForce


def test_all_values_match_request_contract():
    assert {tif.value for tif in TimeInForce} == {"DAY", "GTC", "IOC", "FOK"}


def test_time_in_force_is_a_str_enum():
    assert TimeInForce.DAY == "DAY"
    assert TimeInForce.GTC == "GTC"
    assert TimeInForce.IOC == "IOC"
    assert TimeInForce.FOK == "FOK"


def test_from_string_round_trip():
    assert TimeInForce("GTC") is TimeInForce.GTC
    assert TimeInForce("FOK") is TimeInForce.FOK
