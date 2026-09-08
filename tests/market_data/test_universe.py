"""Tests for A-share ETF/LOF Universe (Instrument Master).

Commit 002 gate: 11 symbols registered, correct exchange/type/
currency/lot_size/tick_size for each, plus Universe API methods.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from services.market_data.domain.instrument import (
    Exchange,
    Instrument,
    InstrumentType,
    TradingStatus,
)
from services.market_data.universe import universe, Universe


SEED_SYMBOLS = [
    "159852", "513050", "159890", "159559", "159569",
    "515880", "159871", "513310", "501225", "161116", "165520",
]

# Authoritative metadata for each seed symbol
EXPECTED = {
    "159852": {"name": "软件ETF",       "exchange": Exchange.SZSE, "type": InstrumentType.ETF},
    "513050": {"name": "中概互联网ETF",  "exchange": Exchange.SSE,  "type": InstrumentType.QDII_ETF},
    "159890": {"name": "云计算ETF",      "exchange": Exchange.SZSE, "type": InstrumentType.ETF},
    "159559": {"name": "机器人ETF",      "exchange": Exchange.SZSE, "type": InstrumentType.ETF},
    "159569": {"name": "港股红利低波ETF","exchange": Exchange.SZSE, "type": InstrumentType.ETF},
    "515880": {"name": "通信ETF",        "exchange": Exchange.SSE,  "type": InstrumentType.ETF},
    "159871": {"name": "有色ETF",        "exchange": Exchange.SZSE, "type": InstrumentType.ETF},
    "513310": {"name": "中韩半导体ETF",  "exchange": Exchange.SSE,  "type": InstrumentType.QDII_ETF},
    "501225": {"name": "全球半导体芯片",  "exchange": Exchange.SSE,  "type": InstrumentType.QDII_LOF},
    "161116": {"name": "易方达黄金主题",  "exchange": Exchange.SZSE, "type": InstrumentType.QDII_LOF},
    "165520": {"name": "中信保诚有色指数","exchange": Exchange.SZSE, "type": InstrumentType.LOF},
}


class TestUniverseRegistration:
    """11/11 symbols registered with correct metadata."""

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_symbol_registered(self, symbol):
        inst = universe.get(symbol)
        assert inst is not None, f"{symbol} not registered"

    def test_count_is_11(self):
        assert universe.count == 11

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_exchange_correct(self, symbol):
        inst = universe.get(symbol)
        assert inst.exchange == EXPECTED[symbol]["exchange"], \
            f"{symbol}: expected {EXPECTED[symbol]['exchange']}, got {inst.exchange}"

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_instrument_type_correct(self, symbol):
        inst = universe.get(symbol)
        assert inst.instrument_type == EXPECTED[symbol]["type"], \
            f"{symbol}: expected {EXPECTED[symbol]['type']}, got {inst.instrument_type}"

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_name_correct(self, symbol):
        inst = universe.get(symbol)
        assert inst.name == EXPECTED[symbol]["name"]

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_currency_cny(self, symbol):
        inst = universe.get(symbol)
        assert inst.currency == "CNY"

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_lot_size_valid(self, symbol):
        inst = universe.get(symbol)
        assert inst.lot_size > 0
        assert inst.lot_size == 100  # A-share standard lot

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_tick_size_valid(self, symbol):
        inst = universe.get(symbol)
        assert inst.tick_size > 0
        assert isinstance(inst.tick_size, Decimal)

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_enabled(self, symbol):
        inst = universe.get(symbol)
        assert inst.enabled is True

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_trading_status_normal(self, symbol):
        inst = universe.get(symbol)
        assert inst.trading_status == TradingStatus.NORMAL


class TestUniverseAPI:
    """Universe registry query methods."""

    def test_get_returns_instrument(self):
        inst = universe.get("159852")
        assert isinstance(inst, Instrument)
        assert inst.symbol == "159852"

    def test_get_unknown_returns_none(self):
        assert universe.get("999999") is None

    def test_all_returns_11(self):
        all_insts = universe.all()
        assert len(all_insts) == 11

    def test_all_returns_instruments(self):
        for inst in universe.all():
            assert isinstance(inst, Instrument)

    def test_enabled_returns_all_11(self):
        enabled = universe.enabled()
        assert len(enabled) == 11
        for inst in enabled:
            assert inst.enabled is True

    def test_by_exchange_szse(self):
        szse = universe.by_exchange(Exchange.SZSE)
        # 159852, 159890, 159559, 159569, 159871, 161116, 165520 = 7
        assert len(szse) == 7
        for inst in szse:
            assert inst.exchange == Exchange.SZSE

    def test_by_exchange_sse(self):
        sse = universe.by_exchange(Exchange.SSE)
        # 513050, 515880, 513310, 501225 = 4
        assert len(sse) == 4
        for inst in sse:
            assert inst.exchange == Exchange.SSE

    def test_by_type_etf(self):
        etfs = universe.by_type(InstrumentType.ETF)
        # 159852, 159890, 159559, 159569, 515880, 159871 = 6
        assert len(etfs) == 6

    def test_by_type_qdii_etf(self):
        qdiis = universe.by_type(InstrumentType.QDII_ETF)
        # 513050, 513310 = 2
        assert len(qdiis) == 2

    def test_by_type_qdii_lof(self):
        qdiis = universe.by_type(InstrumentType.QDII_LOF)
        # 501225, 161116 = 2
        assert len(qdiis) == 2

    def test_by_type_lof(self):
        lofs = universe.by_type(InstrumentType.LOF)
        # 165520 = 1
        assert len(lofs) == 1

    def test_symbols_returns_all_codes(self):
        syms = universe.symbols()
        assert len(syms) == 11
        for s in SEED_SYMBOLS:
            assert s in syms

    def test_contains_known_symbol(self):
        assert universe.contains("159852") is True

    def test_contains_unknown_symbol(self):
        assert universe.contains("999999") is False


class TestUniverseSerialisation:
    """as_list() for API responses."""

    def test_as_list_returns_11_dicts(self):
        items = universe.as_list()
        assert len(items) == 11

    def test_as_list_fields(self):
        items = universe.as_list()
        for item in items:
            assert "symbol" in item
            assert "name" in item
            assert "exchange" in item
            assert "instrument_type" in item
            assert "currency" in item
            assert "lot_size" in item
            assert "tick_size" in item
            assert "enabled" in item

    def test_as_list_exchange_values(self):
        items = universe.as_list()
        exchanges = {i["exchange"] for i in items}
        assert exchanges == {"SZSE", "SSE"}

    def test_as_list_type_values(self):
        items = universe.as_list()
        types = {i["instrument_type"] for i in items}
        assert types == {"ETF", "QDII-ETF", "LOF", "QDII-LOF"}

    def test_as_list_all_cny(self):
        items = universe.as_list()
        for item in items:
            assert item["currency"] == "CNY"


class TestNoDuplicateSymbols:
    """Each symbol appears exactly once."""

    def test_no_duplicates(self):
        syms = universe.symbols()
        assert len(syms) == len(set(syms))
