"""Tests for BrokerQuoteNormalizer (Commit 014 §3 / §8 / §9 / §15)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services.market_data.domain.instrument import Exchange
from services.market_data.exceptions.broker_market_data_error import (
    BrokerErrorCode,
    BrokerMessageError,
)
from services.market_data.normalizers.broker_quote_normalizer import (
    BrokerQuoteNormalizer,
    normalize_symbol,
)

CST = timezone(timedelta(hours=8), "Asia/Shanghai")
TRADING_DAY = date(2026, 9, 8)


def cst_dt(hour=10, minute=31, second=0, microsecond=0) -> datetime:
    return datetime(2026, 9, 8, hour, minute, second, microsecond, tzinfo=CST)


def vendor_frame(**overrides) -> dict:
    """A realistic Chinese-field broker frame (§3)."""
    frame = {
        "证券代码": "159852",
        "证券名称": "软件ETF",
        "最新价": "1.052",
        "买一价": "1.051",
        "卖一价": "1.052",
        "买一量": 1200,
        "卖一量": 3400,
        "成交量": 123400,
        "成交额": "129876.00",
        "昨收": "1.050",
        "开盘": "1.050",
        "最高": "1.060",
        "最低": "1.045",
        "行情时间": cst_dt(),
    }
    frame.update(overrides)
    return frame


@pytest.fixture
def normalizer() -> BrokerQuoteNormalizer:
    return BrokerQuoteNormalizer(name="unit-test")


# ══════════════════════════════════════════════════════════════════
# symbol handling
# ══════════════════════════════════════════════════════════════════


class TestSymbolNormalization:
    @pytest.mark.parametrize(
        "raw",
        ["159852", "SZ159852", "159852.SZ", "sz-159852", " sz159852 ", 159852],
    )
    def test_normalize_symbol_shapes(self, raw):
        assert normalize_symbol(raw) == "159852"

    def test_normalize_symbol_rejects_missing(self):
        with pytest.raises(BrokerMessageError) as excinfo:
            normalize_symbol(None)
        assert excinfo.value.code == BrokerErrorCode.MISSING_SYMBOL.value

    def test_normalize_symbol_rejects_garbage(self):
        with pytest.raises(BrokerMessageError):
            normalize_symbol("no-digits-here")

    def test_symbol_field_is_normalised(self, normalizer):
        quote = normalizer.normalize(vendor_frame(证券代码="SZ159852"))
        assert quote.symbol == "159852"


# ══════════════════════════════════════════════════════════════════
# field mapping (§3 / §15)
# ══════════════════════════════════════════════════════════════════


class TestFieldMapping:
    def test_full_vendor_frame(self, normalizer):
        quote = normalizer.normalize(vendor_frame())
        assert quote.symbol == "159852"
        assert quote.exchange is Exchange.SZSE
        assert quote.last == Decimal("1.052")
        assert quote.bid == Decimal("1.051")
        assert quote.ask == Decimal("1.052")
        assert quote.bid_size == 1200
        assert quote.ask_size == 3400
        assert quote.volume == 123400
        assert quote.turnover == Decimal("129876.00")
        assert quote.open == Decimal("1.050")
        assert quote.high == Decimal("1.060")
        assert quote.low == Decimal("1.045")
        assert quote.pre_close == Decimal("1.050")

    def test_english_canonical_keys(self, normalizer):
        frame = {
            "symbol": "513050",
            "exchange": "SSE",
            "timestamp": cst_dt(),
            "last": 1.62,
            "bid": 1.61,
            "ask": 1.62,
            "bid_size": 100,
            "ask_size": 200,
            "volume": 500,
            "turnover": 810.0,
            "open": 1.60,
            "high": 1.63,
            "low": 1.59,
            "pre_close": 1.60,
        }
        quote = normalizer.normalize(frame)
        assert quote.symbol == "513050"
        assert quote.exchange is Exchange.SSE
        assert quote.last == Decimal("1.62")

    def test_keys_are_case_insensitive(self, normalizer):
        frame = {
            "Symbol": "159890",
            "Timestamp": cst_dt(),
            "Last": "0.950",
        }
        quote = normalizer.normalize(frame)
        assert quote.symbol == "159890"
        assert quote.last == Decimal("0.950")

    def test_custom_field_map_override(self):
        normalizer = BrokerQuoteNormalizer(
            name="vendor-x",
            field_map={"last": ("tradePrice",), "turnover": ("turnOver",)},
        )
        frame = {
            "证券代码": "159559",
            "行情时间": cst_dt(),
            "tradePrice": "0.820",
            "turnOver": "1234.50",
        }
        quote = normalizer.normalize(frame)
        assert quote.last == Decimal("0.820")
        assert quote.turnover == Decimal("1234.50")

    def test_missing_optional_book_defaults_to_zero(self, normalizer):
        frame = vendor_frame()
        for key in ("买一价", "卖一价", "买一量", "卖一量", "成交量", "成交额"):
            del frame[key]
        quote = normalizer.normalize(frame)
        assert quote.bid == Decimal("0")
        assert quote.ask == Decimal("0")
        assert quote.bid_size == 0
        assert quote.ask_size == 0
        assert quote.volume == 0
        assert quote.turnover == Decimal("0")

    def test_thousands_separators_are_accepted(self, normalizer):
        quote = normalizer.normalize(
            vendor_frame(成交量="123,400", 成交额="129,876.00")
        )
        assert quote.volume == 123400
        assert quote.turnover == Decimal("129876.00")

    def test_volume_in_lots_is_converted_to_shares(self):
        normalizer = BrokerQuoteNormalizer(volume_in_lots=True)
        quote = normalizer.normalize(vendor_frame(成交量=1234))
        assert quote.volume == 123400

    def test_received_timestamp_is_stamped(self, normalizer):
        received = cst_dt(10, 31, 0, 45000)
        quote = normalizer.normalize(
            vendor_frame(), received_timestamp=received
        )
        assert quote.received_timestamp == received

    def test_received_timestamp_defaults_to_now(self, normalizer):
        quote = normalizer.normalize(vendor_frame())
        assert quote.received_timestamp is not None
        assert quote.received_timestamp.tzinfo is not None


# ══════════════════════════════════════════════════════════════════
# exchange detection (§9)
# ══════════════════════════════════════════════════════════════════


class TestExchangeMapping:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("SZ", Exchange.SZSE),
            ("szse", Exchange.SZSE),
            ("深交所", Exchange.SZSE),
            ("SH", Exchange.SSE),
            ("SSE", Exchange.SSE),
            ("上交所", Exchange.SSE),
        ],
    )
    def test_explicit_exchange(self, normalizer, raw, expected):
        quote = normalizer.normalize(vendor_frame(交易所=raw))
        assert quote.exchange is expected

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("159852", Exchange.SZSE),
            ("161116", Exchange.SZSE),
            ("165520", Exchange.SZSE),
            ("513050", Exchange.SSE),
            ("515880", Exchange.SSE),
            ("501225", Exchange.SSE),
        ],
    )
    def test_exchange_inferred_from_code(self, normalizer, symbol, expected):
        quote = normalizer.normalize(vendor_frame(证券代码=symbol))
        assert quote.exchange is expected

    def test_unrecognised_exchange_falls_back_to_code_prefix(self, normalizer):
        quote = normalizer.normalize(vendor_frame(交易所="NASDAQ"))
        assert quote.exchange is Exchange.SZSE


# ══════════════════════════════════════════════════════════════════
# timestamps (§8)
# ══════════════════════════════════════════════════════════════════


class TestTimestampMapping:
    def test_aware_datetime_passthrough(self, normalizer):
        ts = cst_dt(10, 35, 1, 123000)
        quote = normalizer.normalize(vendor_frame(行情时间=ts))
        assert quote.timestamp == ts

    def test_naive_datetime_gets_exchange_timezone(self, normalizer):
        naive = datetime(2026, 9, 8, 10, 35, 1)
        quote = normalizer.normalize(vendor_frame(行情时间=naive))
        assert quote.timestamp == naive.replace(tzinfo=CST)

    def test_epoch_seconds(self, normalizer):
        expected = cst_dt(10, 35, 1)
        quote = normalizer.normalize(
            vendor_frame(行情时间=int(expected.timestamp()))
        )
        assert quote.timestamp == expected

    def test_epoch_milliseconds(self, normalizer):
        expected = cst_dt(10, 35, 1)
        quote = normalizer.normalize(
            vendor_frame(行情时间=int(expected.timestamp()) * 1000)
        )
        assert quote.timestamp == expected

    def test_epoch_microseconds(self, normalizer):
        expected = cst_dt(10, 35, 1)
        quote = normalizer.normalize(
            vendor_frame(行情时间=int(expected.timestamp()) * 1_000_000)
        )
        assert quote.timestamp == expected

    def test_epoch_nanoseconds(self, normalizer):
        expected = cst_dt(10, 35, 1)
        quote = normalizer.normalize(
            vendor_frame(行情时间=int(expected.timestamp()) * 1_000_000_000)
        )
        assert quote.timestamp == expected

    def test_compact_datetime_string(self, normalizer):
        quote = normalizer.normalize(vendor_frame(行情时间="20260908103501"))
        assert quote.timestamp == cst_dt(10, 35, 1)

    def test_compact_minute_string(self, normalizer):
        quote = normalizer.normalize(vendor_frame(行情时间="202609081035"))
        assert quote.timestamp == cst_dt(10, 35, 0)

    def test_compact_date_string(self, normalizer):
        quote = normalizer.normalize(vendor_frame(行情时间="20260908"))
        assert quote.timestamp == cst_dt(0, 0, 0)

    def test_iso_string(self, normalizer):
        quote = normalizer.normalize(
            vendor_frame(行情时间="2026-09-08T10:35:01+08:00")
        )
        assert quote.timestamp == cst_dt(10, 35, 1)

    def test_space_separated_string(self, normalizer):
        quote = normalizer.normalize(
            vendor_frame(行情时间="2026-09-08 10:35:01")
        )
        assert quote.timestamp == cst_dt(10, 35, 1)

    def test_time_only_string_uses_trading_date(self, normalizer):
        quote = normalizer.normalize(
            vendor_frame(行情时间="10:35:01"), trading_date=TRADING_DAY
        )
        assert quote.timestamp == cst_dt(10, 35, 1)

    def test_time_only_compact_string_uses_trading_date(self, normalizer):
        quote = normalizer.normalize(
            vendor_frame(行情时间="103501"), trading_date=TRADING_DAY
        )
        assert quote.timestamp == cst_dt(10, 35, 1)

    def test_missing_timestamp_raises(self, normalizer):
        frame = vendor_frame()
        del frame["行情时间"]
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(frame)
        assert excinfo.value.code == BrokerErrorCode.INVALID_TIMESTAMP.value

    @pytest.mark.parametrize("bad", ["not-a-time", "20261308103501", "99:99:99"])
    def test_invalid_timestamp_raises(self, normalizer, bad):
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(vendor_frame(行情时间=bad))
        assert excinfo.value.code == BrokerErrorCode.INVALID_TIMESTAMP.value

    def test_timestamp_is_not_replaced_by_receive_time(self, normalizer):
        """§8 — the exchange timestamp must survive verbatim."""
        exchange_ts = cst_dt(10, 35, 1)
        received = cst_dt(10, 35, 2)
        quote = normalizer.normalize(
            vendor_frame(行情时间=exchange_ts), received_timestamp=received
        )
        assert quote.timestamp == exchange_ts
        assert quote.latency_ms == 1000


# ══════════════════════════════════════════════════════════════════
# malformed payloads (§9)
# ══════════════════════════════════════════════════════════════════


class TestMalformedPayloads:
    @pytest.mark.parametrize("bad", ["a string", 42, ["list"], None])
    def test_non_mapping_raises(self, normalizer, bad):
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(bad)
        assert excinfo.value.code == BrokerErrorCode.MALFORMED_MESSAGE.value

    def test_missing_symbol_raises(self, normalizer):
        frame = vendor_frame()
        del frame["证券代码"]
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(frame)
        assert excinfo.value.code == BrokerErrorCode.MISSING_SYMBOL.value

    def test_missing_price_raises(self, normalizer):
        frame = vendor_frame()
        del frame["最新价"]
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(frame)
        assert excinfo.value.code == BrokerErrorCode.MISSING_PRICE.value

    def test_non_numeric_price_raises(self, normalizer):
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(vendor_frame(最新价="--"))
        assert excinfo.value.code == BrokerErrorCode.INVALID_FIELD.value

    def test_error_payload_is_serialisable(self, normalizer):
        frame = vendor_frame()
        del frame["最新价"]
        with pytest.raises(BrokerMessageError) as excinfo:
            normalizer.normalize(frame)
        payload = excinfo.value.as_dict()
        assert payload["error"] == BrokerErrorCode.MISSING_PRICE.value
        assert payload["symbol"] == "159852"
        assert payload["provider"] == "unit-test"


# ══════════════════════════════════════════════════════════════════
# parsing is not judging (§9)
# ══════════════════════════════════════════════════════════════════


class TestNoSilentSanitising:
    def test_negative_price_is_preserved(self, normalizer):
        """``last = -1`` must reach the Quality Gate unchanged."""
        quote = normalizer.normalize(vendor_frame(最新价="-1"))
        assert quote.last == Decimal("-1")

    def test_zero_price_is_preserved(self, normalizer):
        quote = normalizer.normalize(vendor_frame(最新价="0"))
        assert quote.last == Decimal("0")

    def test_out_of_order_timestamp_is_preserved(self, normalizer):
        old = cst_dt(9, 0, 0)
        quote = normalizer.normalize(vendor_frame(行情时间=old))
        assert quote.timestamp == old

    def test_duplicate_frames_map_identically(self, normalizer):
        """§15 — duplicates are detected downstream, not here."""
        frame = vendor_frame()
        first = normalizer.normalize(frame)
        second = normalizer.normalize(frame)
        assert first.symbol == second.symbol
        assert first.timestamp == second.timestamp
        assert first.last == second.last


class TestNormalizerMetadata:
    def test_as_dict_is_secret_free(self):
        normalizer = BrokerQuoteNormalizer(
            name="vendor-x", volume_in_lots=True
        )
        payload = normalizer.as_dict()
        assert payload["name"] == "vendor-x"
        assert payload["volume_in_lots"] is True
        assert isinstance(payload["timezone"], str) and payload["timezone"]
