"""Tests for MarketDataValidator."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote
from services.market_data.exceptions.market_data_error import (
    InvalidPriceError,
    InvalidQuoteError,
    InvalidSymbolError,
    InvalidTimestampError,
    StaleQuoteError,
    TimestampRegressionError,
)
from services.market_data.validators.market_data_validator import (
    MarketDataValidator,
)


def _good_quote(**overrides) -> MarketQuote:
    defaults = dict(
        symbol="159852",
        exchange=Exchange.SZSE,
        timestamp=datetime.now(timezone.utc),
        last=Decimal("1.234"),
        bid=Decimal("1.233"),
        ask=Decimal("1.234"),
        bid_size=120000,
        ask_size=95000,
        volume=1000000,
    )
    defaults.update(overrides)
    return MarketQuote(**defaults)


class TestValidQuote:
    def test_valid_quote_passes(self):
        validator = MarketDataValidator(stale_seconds=60)
        q = _good_quote()
        result = validator.validate(q)
        assert result is q  # returns same object

    def test_all_11_seed_symbols_pass(self):
        from services.market_data.domain.instrument import Instrument

        validator = MarketDataValidator(stale_seconds=60)
        seeds = [
            "159852", "513050", "159890", "159559", "159569",
            "515880", "159871", "513310", "501225", "161116", "165520",
        ]
        for sym in seeds:
            ex = Instrument.infer_exchange(sym)
            q = _good_quote(symbol=sym, exchange=ex)
            validator.validate(q)  # no exception


class TestInvalidSymbol:
    def test_empty_symbol_rejected(self):
        validator = MarketDataValidator()
        # MarketQuote itself rejects empty symbol at construction time.
        with pytest.raises(ValueError, match="symbol must not be empty"):
            _good_quote(symbol="")

    def test_non_digit_symbol_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidSymbolError, match="6 digits"):
            validator.validate(_good_quote(symbol="ABCDEF"))

    def test_wrong_length_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidSymbolError, match="6 digits"):
            validator.validate(_good_quote(symbol="12345"))

    def test_exchange_mismatch_rejected(self):
        validator = MarketDataValidator()
        # 159852 is SZSE, not SSE
        with pytest.raises(InvalidSymbolError, match="does not match"):
            validator.validate(_good_quote(exchange=Exchange.SSE))


class TestInvalidPrice:
    def test_negative_last_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidPriceError):
            validator.validate(_good_quote(last=Decimal("-0.001")))

    def test_zero_last_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidPriceError, match="below minimum"):
            validator.validate(_good_quote(last=Decimal("0")))

    def test_negative_bid_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidPriceError):
            validator.validate(_good_quote(bid=Decimal("-1.0")))

    def test_negative_ask_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidPriceError):
            validator.validate(_good_quote(ask=Decimal("-1.0")))

    def test_zero_price_allowed_when_configured(self):
        validator = MarketDataValidator(allow_zero_price=True)
        q = _good_quote(
            last=Decimal("0"),
            bid=Decimal("0"),
            ask=Decimal("0"),
        )
        # bid == ask == 0 is ok with allow_zero_price
        validator.validate(q)


class TestBidAskSpread:
    def test_bid_greater_than_ask_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidQuoteError, match="bid.*>.*ask"):
            validator.validate(
                _good_quote(
                    bid=Decimal("1.250"),
                    ask=Decimal("1.240"),
                )
            )

    def test_bid_equals_ask_ok(self):
        validator = MarketDataValidator()
        q = _good_quote(
            bid=Decimal("1.234"),
            ask=Decimal("1.234"),
        )
        validator.validate(q)


class TestInvalidTimestamp:
    def test_naive_timestamp_rejected_at_construction(self):
        # MarketQuote itself rejects naive timestamps
        with pytest.raises(ValueError, match="timezone-aware"):
            _good_quote(timestamp=datetime.now())

    def test_future_timestamp_rejected(self):
        validator = MarketDataValidator()
        future = datetime.now(timezone.utc) + timedelta(seconds=30)
        with pytest.raises(InvalidTimestampError, match="future"):
            validator.validate(_good_quote(timestamp=future))


class TestStaleQuote:
    def test_stale_quote_rejected(self):
        validator = MarketDataValidator(stale_seconds=5)
        old = datetime.now(timezone.utc) - timedelta(seconds=30)
        with pytest.raises(StaleQuoteError, match="old"):
            validator.validate(_good_quote(timestamp=old))

    def test_fresh_quote_within_window_passes(self):
        validator = MarketDataValidator(stale_seconds=120)
        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        validator.validate(_good_quote(timestamp=recent))


class TestNegativeSizes:
    def test_negative_bid_size_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidQuoteError, match="bid_size"):
            validator.validate(_good_quote(bid_size=-1))

    def test_negative_ask_size_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidQuoteError, match="ask_size"):
            validator.validate(_good_quote(ask_size=-1))

    def test_negative_volume_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidQuoteError, match="volume"):
            validator.validate(_good_quote(volume=-100))

    def test_negative_turnover_rejected(self):
        validator = MarketDataValidator()
        with pytest.raises(InvalidQuoteError, match="turnover"):
            validator.validate(
                _good_quote(turnover=Decimal("-1"))
            )


class TestTimestampRegression:
    """Commit 003: timestamp cannot go backwards for a symbol."""

    def test_regression_rejected(self):
        validator = MarketDataValidator(stale_seconds=600)
        t1 = datetime.now(timezone.utc)
        t0 = t1 - timedelta(seconds=10)
        validator.validate(_good_quote(timestamp=t1))
        with pytest.raises(TimestampRegressionError, match="regression"):
            validator.validate(_good_quote(timestamp=t0))

    def test_equal_timestamp_allowed(self):
        validator = MarketDataValidator(stale_seconds=600)
        t = datetime.now(timezone.utc)
        validator.validate(_good_quote(timestamp=t))
        # same timestamp (duplicate delivery) is tolerated
        validator.validate(_good_quote(timestamp=t))

    def test_monotonic_progression_allowed(self):
        validator = MarketDataValidator(stale_seconds=600)
        t = datetime.now(timezone.utc)
        validator.validate(_good_quote(timestamp=t))
        validator.validate(_good_quote(timestamp=t + timedelta(seconds=1)))

    def test_regression_tracked_per_symbol(self):
        validator = MarketDataValidator(stale_seconds=600)
        t1 = datetime.now(timezone.utc)
        t0 = t1 - timedelta(seconds=5)
        # 159852 advances to t1
        validator.validate(_good_quote(timestamp=t1))
        # 513050 arrives with an older clock — its own timeline, fine
        validator.validate(
            _good_quote(symbol="513050", exchange=Exchange.SSE, timestamp=t0)
        )


class TestUniverseCheck:
    def test_outside_universe_rejected_when_enabled(self):
        validator = MarketDataValidator(
            stale_seconds=600, check_universe=True
        )
        # 510050 is a valid SSE fund code but not in the 11-symbol universe
        with pytest.raises(InvalidSymbolError, match="universe"):
            validator.validate(
                _good_quote(symbol="510050", exchange=Exchange.SSE)
            )

    def test_universe_member_accepted(self):
        validator = MarketDataValidator(
            stale_seconds=600, check_universe=True
        )
        validator.validate(_good_quote())  # 159852 is registered

    def test_universe_check_off_by_default(self):
        validator = MarketDataValidator(stale_seconds=600)
        # no universe check by default — only structural checks
        validator.validate(
            _good_quote(symbol="510050", exchange=Exchange.SSE)
        )
