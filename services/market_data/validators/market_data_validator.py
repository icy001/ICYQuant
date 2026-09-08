"""Market quote validator.

Every quote produced by an adapter must pass validation before
entering ICYQuant's downstream pipeline (Strategy, Risk, Paper
Trading).  The validator checks:

1. symbol       — non-empty, 6-digit A-share fund code
2. exchange     — SZSE or SSE
3. timestamp    — timezone-aware, not in the future
4. last, bid, ask — non-negative (Decimal)
5. bid <= ask   — structural consistency
6. bid_size, ask_size, volume — non-negative integers

If a check fails, a specific MarketDataError subclass is raised
so the caller can decide whether to skip, retry, or circuit-break.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from ..domain.instrument import Exchange, Instrument
from ..domain.quote import MarketQuote
from ..exceptions.market_data_error import (
    InvalidPriceError,
    InvalidQuoteError,
    InvalidSymbolError,
    InvalidTimestampError,
    StaleQuoteError,
    TimestampRegressionError,
)


class MarketDataValidator:
    """Validate MarketQuote objects before they enter ICYQuant.

    Usage::

        validator = MarketDataValidator(stale_seconds=30)
        try:
            validator.validate(quote)
        except MarketDataError as exc:
            logger.warning("bad quote: %s", exc)
            continue  # skip
    """

    def __init__(
        self,
        *,
        stale_seconds: int = 60,
        allow_zero_price: bool = False,
        check_universe: bool = False,
    ) -> None:
        self._stale = timedelta(seconds=stale_seconds)
        self._allow_zero_price = allow_zero_price
        self._check_universe = check_universe
        # symbol → last accepted exchange timestamp (monotonicity)
        self._last_ts: dict[str, datetime] = {}

    def validate(self, quote: MarketQuote) -> MarketQuote:
        """Validate a quote.  Raises MarketDataError on failure.

        Returns the same quote on success (for chaining / fluency).
        """
        self._check_symbol(quote)
        self._check_timestamp(quote)
        self._check_prices(quote)
        self._check_sizes(quote)
        self._check_monotonic(quote)
        return quote

    # ── individual checks ────────────────────────────────────────

    def _check_symbol(self, quote: MarketQuote) -> None:
        if not quote.symbol:
            raise InvalidSymbolError("symbol is empty")
        if not quote.symbol.isdigit() or len(quote.symbol) != 6:
            raise InvalidSymbolError(
                f"invalid A-share fund code: {quote.symbol!r} "
                f"(expected 6 digits)"
            )
        # Verify exchange matches code prefix
        try:
            expected = Instrument.infer_exchange(quote.symbol)
        except ValueError as exc:
            raise InvalidSymbolError(str(exc))
        if quote.exchange != expected:
            raise InvalidSymbolError(
                f"exchange {quote.exchange.value} does not match "
                f"symbol prefix {quote.symbol[:2]}"
            )
        # Universe membership (optional)
        if self._check_universe:
            from ..universe import universe

            if not universe.contains(quote.symbol):
                raise InvalidSymbolError(
                    f"symbol {quote.symbol} is not in the trading universe"
                )

    def _check_timestamp(self, quote: MarketQuote) -> None:
        if quote.timestamp.tzinfo is None:
            raise InvalidTimestampError(
                "timestamp is not timezone-aware"
            )
        now = datetime.now(timezone.utc)
        # Future check: allow up to 5 seconds clock drift
        if quote.timestamp > now + timedelta(seconds=5):
            raise InvalidTimestampError(
                f"timestamp is in the future: {quote.timestamp.isoformat()}"
            )
        # Stale check
        age = now - quote.timestamp
        if age > self._stale:
            raise StaleQuoteError(
                f"quote is {age.total_seconds():.0f}s old "
                f"(max {self._stale.total_seconds():.0f}s)"
            )

    def _check_prices(self, quote: MarketQuote) -> None:
        min_val = Decimal("0") if self._allow_zero_price else Decimal("0.001")

        for field_name, value in [
            ("last", quote.last),
            ("bid", quote.bid),
            ("ask", quote.ask),
        ]:
            if not isinstance(value, Decimal):
                raise InvalidPriceError(
                    f"{field_name} is not a Decimal: {type(value).__name__}"
                )
            if value < min_val:
                raise InvalidPriceError(
                    f"{field_name} = {value} is below minimum {min_val}"
                )

        if quote.bid > quote.ask:
            raise InvalidQuoteError(
                f"bid ({quote.bid}) > ask ({quote.ask})"
            )

    def _check_sizes(self, quote: MarketQuote) -> None:
        for name, value in [
            ("bid_size", quote.bid_size),
            ("ask_size", quote.ask_size),
            ("volume", quote.volume),
        ]:
            if value < 0:
                raise InvalidQuoteError(
                    f"{name} = {value} is negative"
                )
        if quote.turnover < 0:
            raise InvalidQuoteError(
                f"turnover = {quote.turnover} is negative"
            )

    def _check_monotonic(self, quote: MarketQuote) -> None:
        """Reject exchange-timestamp regression (older tick arriving
        after a newer one for the same symbol)."""
        prev = self._last_ts.get(quote.symbol)
        if prev is not None and quote.timestamp < prev:
            raise TimestampRegressionError(
                f"timestamp regression for {quote.symbol}: "
                f"{quote.timestamp.isoformat()} < "
                f"{prev.isoformat()}"
            )
        if prev is None or quote.timestamp > prev:
            self._last_ts[quote.symbol] = quote.timestamp


__all__ = ["MarketDataValidator"]
