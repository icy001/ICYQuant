"""Market data adapter interface.

This is the single contract between ICYQuant and any external
market data source (broker, exchange, third-party feed).  Every
adapter — Mock, broker A, provider B — must implement this
interface.  Downstream code (Strategy, Risk, Paper Trading) never
imports an adapter directly; it only sees MarketQuote objects
produced by ``stream()``.

Design principle: swapping Mock → Real broker must not require
changing a single line in Strategy, Risk, Position, Ledger, or
Dashboard.  This is what makes Paper → Shadow → Live possible.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Optional

from ..domain.quote import MarketQuote
from ..exceptions.market_data_error import (
    AdapterAlreadyConnectedError,
    AdapterNotConnectedError,
)


class MarketDataAdapter(ABC):
    """Abstract base for all market data adapters.

    Lifecycle::

        connect()
            ↓
        subscribe(["159852", "513050", ...])
            ↓
        stream()  →  Iterator[MarketQuote]
            ↓
        unsubscribe(["159852"])
            ↓
        disconnect()

    Thread-safety: adapters are not required to be thread-safe.
    The caller (pipeline / feed loop) drives a single thread.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name (e.g. 'mock', 'broker-A')."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether the adapter is currently connected."""

    @abstractmethod
    def connect(self) -> None:
        """Establish the underlying connection.

        Raises AdapterAlreadyConnectedError if called when already
        connected.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the underlying connection.

        Safe to call when not connected (no-op).
        """

    @abstractmethod
    def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to real-time quotes for the given symbols.

        Raises AdapterNotConnectedError if called before connect().
        """

    @abstractmethod
    def unsubscribe(self, symbols: list[str]) -> None:
        """Stop receiving quotes for the given symbols.

        No-op for symbols not currently subscribed.
        """

    @abstractmethod
    def stream(self) -> Iterator[MarketQuote]:
        """Yield validated MarketQuote objects for subscribed symbols.

        Raises AdapterNotConnectedError if called before connect().

        This is a blocking generator — the caller drives the pull
        loop.  The adapter blocks until the next quote is available
        (or yields control on timeout in real adapters).
        """

    # ── guard helpers for subclasses ────────────────────────────
    def _require_connected(self) -> None:
        if not self.connected:
            raise AdapterNotConnectedError(
                f"{self.name}: operation requires connect() first"
            )

    def _require_disconnected(self) -> None:
        if self.connected:
            raise AdapterAlreadyConnectedError(
                f"{self.name}: already connected"
            )


__all__ = ["MarketDataAdapter"]
