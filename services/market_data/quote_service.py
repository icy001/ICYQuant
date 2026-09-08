"""Quote Service — the real-time quote pipeline hub.

Pipeline (Commit 003)::

    MarketDataAdapter  →  QuoteNormalizer (inside adapter)
                       →  QuoteValidator
                       →  QuoteService (latest quote per symbol)
                       →  Backend API
                       →  Frontend

QuoteService holds the latest validated MarketQuote per symbol and
computes freshness (FRESH / WARNING / STALE / OFFLINE) against
configurable thresholds.  QuoteFeed drives any adapter in a
background thread, pushing each streamed quote through validation
into the service.

Phase 1 uses MockMarketDataAdapter; swapping in a real broker
adapter later requires no changes downstream (the Paper → Shadow →
Live swap point).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .adapters.base import MarketDataAdapter
from .domain.instrument import Exchange
from .domain.quote import MarketQuote, QuoteFreshness
from .exceptions.market_data_error import MarketDataError
from .validators.market_data_validator import MarketDataValidator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FreshnessThresholds:
    """Configurable freshness windows (seconds)."""

    fresh_seconds: float = 3.0
    stale_seconds: float = 10.0


class QuoteService:
    """Latest-quote cache with freshness classification.

    Thread-safe: QuoteFeed writes from its background thread while
    API handlers read concurrently.
    """

    def __init__(
        self,
        *,
        validator: Optional[MarketDataValidator] = None,
        thresholds: Optional[FreshnessThresholds] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._quotes: dict[str, MarketQuote] = {}
        self._validator = validator or MarketDataValidator(
            stale_seconds=600
        )
        self._thresholds = thresholds or FreshnessThresholds()
        # stats
        self._accepted = 0
        self._rejected = 0

    # ── write path ──────────────────────────────────────────────

    def update(self, quote: MarketQuote) -> MarketQuote:
        """Validate + store the latest quote for its symbol.

        Stamps ``received_timestamp`` with the ICYQuant receive time.
        Invalid quotes are rejected (exception propagates) and never
        stored.  Quote age is NOT re-validated here beyond the
        validator's staleness window so that old quotes can still be
        queried for display (as STALE) — freshness is computed at
        read time instead.
        """
        self._validator.validate(quote)
        received = datetime.now(timezone.utc)
        if quote.received_timestamp is None:
            quote = replace(quote, received_timestamp=received)
        with self._lock:
            self._quotes[quote.symbol] = quote
            self._accepted += 1
        return quote

    # ── read path ───────────────────────────────────────────────

    def latest(self, symbol: str) -> Optional[MarketQuote]:
        with self._lock:
            return self._quotes.get(symbol)

    def _view(
        self, quote: Optional[MarketQuote], symbol: str
    ) -> dict:
        """Build the API view for one symbol (quote + freshness)."""
        if quote is None:
            return {
                "symbol": symbol,
                "status": QuoteFreshness.OFFLINE.value,
                "quote": None,
                "age_seconds": None,
            }
        age = quote.age_seconds()
        freshness = quote.freshness(
            fresh_seconds=self._thresholds.fresh_seconds,
            stale_seconds=self._thresholds.stale_seconds,
        )
        data = quote.as_dict()
        data["age_seconds"] = round(age, 2)
        data["freshness"] = freshness.value
        # display status: LIVE for FRESH, else freshness itself
        data["status"] = "LIVE" if freshness == QuoteFreshness.FRESH else freshness.value
        return {
            "symbol": symbol,
            "status": data["status"],
            "quote": data,
            "age_seconds": round(age, 2),
        }

    def snapshot(self, symbols: Optional[list[str]] = None) -> list[dict]:
        """Latest quote views for the given symbols (default: all
        symbols that have quotes)."""
        if symbols is None:
            with self._lock:
                symbols = sorted(self._quotes.keys())
        views = []
        for sym in symbols:
            with self._lock:
                quote = self._quotes.get(sym)
            views.append(self._view(quote, sym))
        return views

    def stats(self) -> dict:
        with self._lock:
            return {
                "symbols_tracked": len(self._quotes),
                "quotes_accepted": self._accepted,
                "quotes_rejected": self._rejected,
                "thresholds": {
                    "fresh_seconds": self._thresholds.fresh_seconds,
                    "stale_seconds": self._thresholds.stale_seconds,
                },
            }

    def mark_rejected(self) -> None:
        with self._lock:
            self._rejected += 1

    def reset(self) -> None:
        with self._lock:
            self._quotes.clear()
            self._accepted = 0
            self._rejected = 0


class QuoteFeed:
    """Drives a MarketDataAdapter in a background thread, pushing
    every streamed quote through QuoteService.update().

    Usage::

        feed = QuoteFeed(adapter, service)
        feed.start(symbols=["159852", ...], interval=0.2)
        ...
        feed.stop()
    """

    def __init__(
        self,
        adapter: MarketDataAdapter,
        service: QuoteService,
        *,
        interval: float = 0.2,
    ) -> None:
        self._adapter = adapter
        self._service = service
        self._interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, symbols: list[str], interval: Optional[float] = None) -> None:
        if self.running:
            return
        if interval is not None:
            self._interval = interval
        self._stop.clear()
        if not self._adapter.connected:
            self._adapter.connect()
        self._adapter.subscribe(symbols)

        def run() -> None:
            logger.info(
                "QuoteFeed started: %d symbols via %s adapter",
                len(symbols), self._adapter.name,
            )
            try:
                for quote in self._adapter.stream():
                    if self._stop.is_set():
                        break
                    try:
                        self._service.update(quote)
                    except MarketDataError as exc:
                        self._service.mark_rejected()
                        logger.warning("quote rejected: %s", exc)
                    if self._stop.is_set():
                        break
                    self._stop.wait(self._interval)
            finally:
                logger.info("QuoteFeed stopped")

        self._thread = threading.Thread(
            target=run, name="quote-feed", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        if self._adapter.connected:
            self._adapter.disconnect()


# ── Singleton used by the Dashboard API ─────────────────────────
quote_service = QuoteService()

__all__ = [
    "QuoteService",
    "QuoteFeed",
    "FreshnessThresholds",
    "quote_service",
]
