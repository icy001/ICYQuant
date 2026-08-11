"""
Market Data Adapter — Connects Strategy Platform to market data services.

Provides standardized interface for real-time and historical market data
including quotes, bars, order books, and reference data.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MarketDataType(str, Enum):
    """Types of market data."""
    QUOTE = "quote"
    BAR = "bar"
    ORDER_BOOK = "order_book"
    TRADE = "trade"
    REFERENCE = "reference"
    FUNDAMENTAL = "fundamental"


@dataclass
class MarketDataRequest:
    """Request for market data."""
    strategy_id: str
    data_type: MarketDataType
    instruments: list[str]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    interval: str = "1m"  # 1s, 1m, 5m, 1h, 1d
    fields: list[str] = field(default_factory=list)
    max_staleness_seconds: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketDataSnapshot:
    """Market data snapshot result."""
    request_id: str
    data_type: MarketDataType
    instruments: dict[str, Any] = field(default_factory=dict)  # instrument -> data
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_stale: bool = False
    fetch_latency_ms: float = 0.0
    error: Optional[str] = None


class MarketDataAdapter:
    """
    Adapter for market data services.

    Provides async interface for fetching quotes, bars, order books,
    and reference data with staleness checks and caching.

    Usage::

        adapter = MarketDataAdapter()
        await adapter.initialize()
        snapshot = await adapter.fetch_data(MarketDataRequest(
            strategy_id="strat_001",
            data_type=MarketDataType.QUOTE,
            instruments=["AAPL", "GOOGL"],
        ))
    """

    def __init__(self) -> None:
        self._data_cache: dict[str, MarketDataSnapshot] = {}
        self._request_count: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the market data adapter."""
        self._initialized = True
        logger.info("MarketDataAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("MarketDataAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def fetch_data(self, request: MarketDataRequest) -> MarketDataSnapshot:
        """Fetch market data for a strategy."""
        self._request_count += 1
        request_id = f"md_{self._request_count:06d}"

        start = asyncio.get_event_loop().time()

        # Check cache
        cache_key = f"{request.data_type.value}:{','.join(sorted(request.instruments))}"
        cached = self._data_cache.get(cache_key)

        if cached and not self._is_stale(cached, request.max_staleness_seconds):
            latency = (asyncio.get_event_loop().time() - start) * 1000
            cached.fetch_latency_ms = latency
            return cached

        # Simulate market data fetch
        data: dict[str, Any] = {}
        for instrument in request.instruments:
            data[instrument] = {
                "symbol": instrument,
                "data_type": request.data_type.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "available",
            }

        latency = (asyncio.get_event_loop().time() - start) * 1000

        snapshot = MarketDataSnapshot(
            request_id=request_id,
            data_type=request.data_type,
            instruments=data,
            fetch_latency_ms=latency,
        )
        self._data_cache[cache_key] = snapshot

        logger.debug(f"Market data fetched: {len(request.instruments)} instruments, type={request.data_type.value}")
        return snapshot

    async def get_latest_quote(self, instrument: str) -> Optional[dict[str, Any]]:
        """Get the latest quote for a single instrument."""
        request = MarketDataRequest(
            strategy_id="direct",
            data_type=MarketDataType.QUOTE,
            instruments=[instrument],
        )
        snapshot = await self.fetch_data(request)
        return snapshot.instruments.get(instrument)

    async def get_latest_bar(
        self,
        instrument: str,
        interval: str = "1m",
    ) -> Optional[dict[str, Any]]:
        """Get the latest bar for a single instrument."""
        request = MarketDataRequest(
            strategy_id="direct",
            data_type=MarketDataType.BAR,
            instruments=[instrument],
            interval=interval,
        )
        snapshot = await self.fetch_data(request)
        return snapshot.instruments.get(instrument)

    async def invalidate_cache(self) -> None:
        """Invalidate cached market data."""
        self._data_cache.clear()
        logger.info("Market data cache invalidated.")

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "cache_entries": len(self._data_cache),
            "requests_served": self._request_count,
        }

    @staticmethod
    def _is_stale(snapshot: MarketDataSnapshot, max_staleness: float) -> bool:
        """Check if a snapshot is stale."""
        age = (datetime.now(timezone.utc) - snapshot.timestamp).total_seconds()
        return age > max_staleness
