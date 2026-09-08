"""Market data error types.

Every bad quote that tries to enter ICYQuant gets a specific
exception so the caller (adapter, pipeline, strategy) can decide
whether to skip, retry, or circuit-break — instead of silently
passing garbage downstream.
"""
from __future__ import annotations


class MarketDataError(Exception):
    """Base for all market-data validation / adapter errors."""


class InvalidQuoteError(MarketDataError):
    """A quote field is missing, empty, or structurally invalid."""


class InvalidPriceError(MarketDataError):
    """last / bid / ask is negative or otherwise impossible."""


class InvalidTimestampError(MarketDataError):
    """Timestamp is missing, not a datetime, or in the future."""


class InvalidSymbolError(MarketDataError):
    """Symbol is empty or does not match a registered instrument."""


class StaleQuoteError(MarketDataError):
    """Quote timestamp is older than the configured staleness window."""


class TimestampRegressionError(MarketDataError):
    """Quote timestamp went backwards for the same symbol."""


class AdapterNotConnectedError(MarketDataError):
    """subscribe / stream called before connect()."""


class AdapterAlreadyConnectedError(MarketDataError):
    """connect() called when already connected."""


class QualityRejectedError(MarketDataError):
    """The Quality Gate rejected the data (Commit 006).

    The verdict and the quarantined payload live on the gate; this
    exception only signals the write path (QuoteFeed / BarService)
    that the item must not flow downstream.
    """

    def __init__(self, symbol: str, status: str, reasons: str) -> None:
        self.symbol = symbol
        self.status = status
        self.reasons = reasons
        super().__init__(
            f"quality gate rejected {symbol}: {status} ({reasons})"
        )


__all__ = [
    "MarketDataError",
    "InvalidQuoteError",
    "InvalidPriceError",
    "InvalidTimestampError",
    "InvalidSymbolError",
    "StaleQuoteError",
    "TimestampRegressionError",
    "AdapterNotConnectedError",
    "AdapterAlreadyConnectedError",
    "QualityRejectedError",
]
