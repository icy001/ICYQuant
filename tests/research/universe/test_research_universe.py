"""Tests for Research Universe v1.1 (nine core research assets)."""
from __future__ import annotations

import pytest

from research.universe.research_universe import (
    RESEARCH_UNIVERSE_V1_1,
    by_class,
    by_symbol,
    symbols,
)

EXPECTED_SYMBOLS = [
    "NVDA", "SPY", "QQQ", "000688.SH", "HSTECH",
    "EURUSD", "XAUUSD", "AU", "AG",
]


def test_universe_has_nine_assets():
    assert len(RESEARCH_UNIVERSE_V1_1) == 9
    assert symbols() == EXPECTED_SYMBOLS


@pytest.mark.parametrize("symbol", EXPECTED_SYMBOLS)
def test_by_symbol_resolves(symbol):
    asset = by_symbol(symbol)
    assert asset.symbol == symbol
    assert asset.timezone
    assert asset.session is not None


def test_by_symbol_unknown_raises():
    with pytest.raises(KeyError):
        by_symbol("NOPE")


def test_asset_classes():
    equity = by_class("equity")
    fx = by_class("fx")
    metals = by_class("precious_metal")
    assert [a.symbol for a in equity] == ["NVDA", "SPY", "QQQ", "000688.SH", "HSTECH"]
    assert [a.symbol for a in fx] == ["EURUSD"]
    assert [a.symbol for a in metals] == ["XAUUSD", "AU", "AG"]


def test_shfe_futures_are_continuous_contracts():
    for symbol in ("AU", "AG"):
        asset = by_symbol(symbol)
        assert asset.continuous_contract is True
        assert asset.exchange == "SHFE"
        assert asset.timezone == "Asia/Shanghai"


def test_equity_assets_use_asset_class_equity():
    for symbol in ("NVDA", "SPY", "QQQ", "000688.SH", "HSTECH"):
        assert by_symbol(symbol).asset_class == "equity"


def test_24h_markets_use_rollover_session():
    for symbol in ("EURUSD", "XAUUSD"):
        session = by_symbol(symbol).session
        assert session is not None
        assert session.rollover is True
