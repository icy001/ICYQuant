"""Tests for ControlScope (spec section 4)."""
from __future__ import annotations

from services.control_plane.controls.scope import ControlScope


def test_scope_values():
    assert ControlScope.GLOBAL.value == "GLOBAL"
    assert ControlScope.ACCOUNT.value == "ACCOUNT"
    assert ControlScope.PORTFOLIO.value == "PORTFOLIO"
    assert ControlScope.STRATEGY.value == "STRATEGY"
    assert ControlScope.SYMBOL.value == "SYMBOL"
    assert ControlScope.VENUE.value == "VENUE"
    assert ControlScope.ORDER.value == "ORDER"


def test_scope_is_str_enum():
    assert str(ControlScope.SYMBOL) == "ControlScope.SYMBOL"
    assert ControlScope("SYMBOL") is ControlScope.SYMBOL


def test_scope_covers_all_control_levels():
    expected = {
        "GLOBAL",
        "ACCOUNT",
        "PORTFOLIO",
        "STRATEGY",
        "SYMBOL",
        "VENUE",
        "ORDER",
    }

    assert {scope.value for scope in ControlScope} == expected
