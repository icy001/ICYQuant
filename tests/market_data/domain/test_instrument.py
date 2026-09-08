"""Tests for A-share ETF/LOF Instrument domain model."""
from __future__ import annotations

import pytest

from services.market_data.domain.instrument import (
    Exchange,
    Instrument,
    InstrumentType,
    TradingStatus,
)


# ── 11 seed symbols ───────────────────────────────────────────

SEED_SYMBOLS = [
    "159852", "513050", "159890", "159559", "159569",
    "515880", "159871", "513310", "501225", "161116", "165520",
]


class TestInstrumentType:
    def test_all_types_exist(self):
        assert InstrumentType.ETF == "ETF"
        assert InstrumentType.QDII_ETF == "QDII-ETF"
        assert InstrumentType.LOF == "LOF"
        assert InstrumentType.QDII_LOF == "QDII-LOF"


class TestExchange:
    def test_szse_and_sse(self):
        assert Exchange.SZSE == "SZSE"
        assert Exchange.SSE == "SSE"


class TestInferExchange:
    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_all_seed_symbols_resolve(self, symbol):
        """All 11 seed symbols can be resolved to an exchange."""
        ex = Instrument.infer_exchange(symbol)
        assert ex in (Exchange.SZSE, Exchange.SSE)

    def test_szse_prefix_15(self):
        assert Instrument.infer_exchange("159852") == Exchange.SZSE

    def test_szse_prefix_16(self):
        assert Instrument.infer_exchange("161116") == Exchange.SZSE

    def test_sse_prefix_50(self):
        assert Instrument.infer_exchange("501225") == Exchange.SSE

    def test_sse_prefix_51(self):
        assert Instrument.infer_exchange("513050") == Exchange.SSE

    def test_invalid_code_raises(self):
        with pytest.raises(ValueError, match="invalid A-share fund code"):
            Instrument.infer_exchange("12345")

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="invalid A-share fund code"):
            Instrument.infer_exchange("1234567")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="invalid A-share fund code"):
            Instrument.infer_exchange("")

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError, match="cannot infer exchange"):
            Instrument.infer_exchange("300001")


class TestInferType:
    def test_qdii_etf_513050(self):
        assert Instrument.infer_type("513050") == InstrumentType.QDII_ETF

    def test_qdii_etf_513310(self):
        assert Instrument.infer_type("513310") == InstrumentType.QDII_ETF

    def test_etf_159871(self):
        assert Instrument.infer_type("159871") == InstrumentType.ETF

    def test_qdii_lof_165520(self):
        assert Instrument.infer_type("165520") == InstrumentType.QDII_LOF

    def test_qdii_lof_501225(self):
        assert Instrument.infer_type("501225") == InstrumentType.QDII_LOF

    def test_qdii_lof_161116(self):
        assert Instrument.infer_type("161116") == InstrumentType.QDII_LOF

    def test_etf_default_15(self):
        assert Instrument.infer_type("159852") == InstrumentType.ETF

    def test_etf_default_51(self):
        assert Instrument.infer_type("515880") == InstrumentType.ETF


class TestInstrumentCreation:
    def test_create_basic(self):
        inst = Instrument(
            symbol="159852",
            exchange=Exchange.SZSE,
            instrument_type=InstrumentType.ETF,
        )
        assert inst.symbol == "159852"
        assert inst.exchange == Exchange.SZSE
        assert inst.instrument_type == InstrumentType.ETF
        assert inst.currency == "CNY"
        assert inst.lot_size == 100
        assert inst.trading_status == TradingStatus.NORMAL

    def test_create_with_all_fields(self):
        inst = Instrument(
            symbol="513050",
            exchange=Exchange.SSE,
            instrument_type=InstrumentType.QDII_ETF,
            currency="CNY",
            lot_size=100,
            trading_status=TradingStatus.HALTED,
            name="中证500ETF",
        )
        assert inst.name == "中证500ETF"
        assert inst.trading_status == TradingStatus.HALTED

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol must not be empty"):
            Instrument(
                symbol="",
                exchange=Exchange.SZSE,
                instrument_type=InstrumentType.ETF,
            )

    @pytest.mark.parametrize("symbol", SEED_SYMBOLS)
    def test_all_11_seed_symbols_can_register(self, symbol):
        """All 11 symbols can be registered as Instrument objects."""
        ex = Instrument.infer_exchange(symbol)
        it = Instrument.infer_type(symbol)
        inst = Instrument(
            symbol=symbol,
            exchange=ex,
            instrument_type=it,
        )
        assert inst.symbol == symbol
        assert inst.exchange in (Exchange.SZSE, Exchange.SSE)
        assert inst.instrument_type in (
            InstrumentType.ETF,
            InstrumentType.QDII_ETF,
            InstrumentType.LOF,
            InstrumentType.QDII_LOF,
        )
        assert inst.currency == "CNY"
