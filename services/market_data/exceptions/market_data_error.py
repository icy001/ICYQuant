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
]
