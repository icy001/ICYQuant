"""
Real-Time PnL Engine — Millisecond-level profit & loss computation.

Computes floating (unrealized) PnL, realized PnL, and portfolio-level
PnL aggregation from position updates and market data streams.

Architecture::

    Trades → Market Price → Floating PnL → Realized PnL → Portfolio PnL
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PnLSnapshot:
    """Point-in-time PnL snapshot for a single position."""
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    pnl_pct: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PortfolioPnL:
    """Aggregated portfolio PnL across all positions."""
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    ytd_pnl: float = 0.0
    winning_positions: int = 0
    losing_positions: int = 0
    positions: dict[str, PnLSnapshot] = field(default_factory=dict)
    pnl_history: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RealtimePnLEngine:
    """
    Real-time PnL computation engine with millisecond-level updates.

    Computes floating PnL from position × (market_price - avg_cost),
    tracks realized PnL from trade fills, and aggregates to portfolio
    level. Maintains a rolling PnL history for drawdown computation.

    Usage::

        engine = RealtimePnLEngine()
        await engine.initialize()

        # Update market price
        await engine.update_price("AAPL", 150.25)

        # Compute PnL
        pnl = await engine.compute_position_pnl("AAPL", quantity=100, avg_cost=145.0)

        # Get portfolio PnL
        portfolio = await engine.get_portfolio_pnl()
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._positions: dict[str, PnLSnapshot] = {}
        self._prices: dict[str, float] = {}
        self._realized_pnl: dict[str, float] = {}
        self._pnl_history: deque[float] = deque(maxlen=max_history)
        self._daily_start_pnl: float = 0.0
        self._weekly_start_pnl: float = 0.0
        self._monthly_start_pnl: float = 0.0
        self._lock = asyncio.Lock()
        self._update_count: int = 0
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the PnL engine."""
        self._initialized = True
        logger.info("RealtimePnLEngine initialized.")

    async def stop(self) -> None:
        """Stop the PnL engine."""
        self._initialized = False
        logger.info("RealtimePnLEngine stopped.")

    # ---- Core API ----

    async def update_price(self, symbol: str, price: float) -> None:
        """
        Update market price for a symbol.

        Triggers recalculation of unrealized PnL for any position
        held in this symbol.
        """
        async with self._lock:
            self._prices[symbol] = price
            self._update_count += 1

            # Recalculate position PnL if we hold this symbol
            if symbol in self._positions:
                pos = self._positions[symbol]
                pos.market_price = price
                pos.market_value = pos.quantity * price
                pos.unrealized_pnl = pos.quantity * (price - pos.avg_cost)
                if pos.avg_cost != 0:
                    pos.pnl_pct = ((price - pos.avg_cost) / abs(pos.avg_cost)) * 100

    async def compute_position_pnl(
        self,
        symbol: str,
        quantity: float,
        avg_cost: float,
    ) -> PnLSnapshot:
        """Compute PnL for a single position."""
        async with self._lock:
            market_price = self._prices.get(symbol, avg_cost)
            market_value = quantity * market_price
            unrealized_pnl = quantity * (market_price - avg_cost)
            pnl_pct = ((market_price - avg_cost) / abs(avg_cost)) * 100 if avg_cost != 0 else 0.0
            realized_pnl = self._realized_pnl.get(symbol, 0.0)

            snapshot = PnLSnapshot(
                symbol=symbol,
                quantity=quantity,
                avg_cost=avg_cost,
                market_price=market_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                pnl_pct=pnl_pct,
            )
            self._positions[symbol] = snapshot
            return snapshot

    async def record_realized_pnl(self, symbol: str, pnl: float) -> None:
        """Record realized PnL from a trade fill."""
        async with self._lock:
            current = self._realized_pnl.get(symbol, 0.0)
            self._realized_pnl[symbol] = current + pnl

    async def get_portfolio_pnl(self) -> PortfolioPnL:
        """Get aggregated portfolio PnL across all positions."""
        total_unrealized = 0.0
        total_realized = 0.0
        winning = 0
        losing = 0

        async with self._lock:
            for pos in self._positions.values():
                total_unrealized += pos.unrealized_pnl
                total_realized += pos.realized_pnl
                if pos.unrealized_pnl > 0:
                    winning += 1
                elif pos.unrealized_pnl < 0:
                    losing += 1

        total = total_unrealized + total_realized
        self._pnl_history.append(total)

        return PortfolioPnL(
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            daily_pnl=total - self._daily_start_pnl,
            weekly_pnl=total - self._weekly_start_pnl,
            monthly_pnl=total - self._monthly_start_pnl,
            winning_positions=winning,
            losing_positions=losing,
            positions=dict(self._positions),
            pnl_history=self._pnl_history.copy(),
        )

    async def get_position_pnl(self, symbol: str) -> Optional[PnLSnapshot]:
        """Get PnL for a specific position."""
        return self._positions.get(symbol)

    async def set_baselines(
        self,
        daily: float = 0.0,
        weekly: float = 0.0,
        monthly: float = 0.0,
    ) -> None:
        """Set baseline PnL for period comparisons."""
        self._daily_start_pnl = daily
        self._weekly_start_pnl = weekly
        self._monthly_start_pnl = monthly

    async def reset(self) -> None:
        """Reset all PnL state."""
        async with self._lock:
            self._positions.clear()
            self._realized_pnl.clear()
            self._pnl_history.clear()
            self._daily_start_pnl = 0.0
            self._weekly_start_pnl = 0.0
            self._monthly_start_pnl = 0.0
            self._update_count = 0
        logger.info("RealtimePnLEngine reset.")

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        async with self._lock:
            return {
                "tracked_symbols": len(self._positions),
                "tracked_prices": len(self._prices),
                "price_updates": self._update_count,
                "pnl_history_length": len(self._pnl_history),
            }

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "tracked_positions": len(self._positions),
            "price_updates": self._update_count,
        }
