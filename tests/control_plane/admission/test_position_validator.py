"""Tests for PositionEffectValidator (spec sections 10/11/12)."""
from __future__ import annotations

import pytest

from services.control_plane.admission.position_validator import (
    PositionEffect,
    PositionEffectValidator,
)


@pytest.fixture
def validator():
    return PositionEffectValidator()


def test_zero_position_is_always_increase(validator):
    assert (
        validator.evaluate(0, "BUY", 100)
        is PositionEffect.INCREASE
    )
    assert (
        validator.evaluate(0, "SELL", 100)
        is PositionEffect.INCREASE
    )


def test_buy_reduces_short_position(validator):
    assert (
        validator.evaluate(-100, "BUY", 50)
        is PositionEffect.REDUCE
    )


def test_buy_increases_long_position(validator):
    assert (
        validator.evaluate(100, "BUY", 50)
        is PositionEffect.INCREASE
    )


def test_sell_reduces_long_position(validator):
    assert (
        validator.evaluate(100, "SELL", 50)
        is PositionEffect.REDUCE
    )


def test_sell_increases_short_position(validator):
    assert (
        validator.evaluate(-100, "SELL", 50)
        is PositionEffect.INCREASE
    )


def test_sell_flattens_long_position(validator):
    assert (
        validator.evaluate(100, "SELL", 100)
        is PositionEffect.FLATTEN
    )


def test_buy_flattens_short_position(validator):
    assert (
        validator.evaluate(-100, "BUY", 100)
        is PositionEffect.FLATTEN
    )


def test_side_is_case_insensitive(validator):
    assert (
        validator.evaluate(100, "sell", 50)
        is PositionEffect.REDUCE
    )
    assert (
        validator.evaluate(100, "BUY", 50)
        is PositionEffect.INCREASE
    )


def test_oversell_still_reduces_net_exposure(validator):
    # +100 short of -50: net long exposure decreased, still a REDUCE.
    assert (
        validator.evaluate(100, "SELL", 150)
        is PositionEffect.REDUCE
    )
