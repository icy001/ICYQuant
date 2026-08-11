"""
Position Monitor — Real-time position-level risk monitoring.

Monitors individual position sizes, PnL, duration, and risk
contribution. Detects oversized positions and provides position-
level risk analytics.

Architecture::

    Position Updates → Size Check → PnL Check → Duration Check → Risk Contribution
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """Detailed information about a single position."""
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_pct: float = 0.0
    weight_pct: float = 0.0
    holding_duration_hours: float = 0.0
    risk_contribution: float = 0.0
    side: str = "LONG"
    asset_class: str = "EQUITY"
    sector: str = ""
    opened_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PositionAlert:
    """Alert generated for a specific position."""
    symbol: str
    alert_type: str
    severity: str
    message: str
    current_value: float
    limit: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PositionMonitor:
    """
    Real-time position-level risk monitor.

    Tracks individual positions for size limits, PnL thresholds,
    holding duration, and risk contribution. Generates position-level
    alerts when limits are breached.

    Usage::

        monitor = PositionMonitor(config={...})
        await monitor.initialize()

        alerts = await monitor.evaluate_position("AAPL", qty=1000, price=150, ...)
    """

    def __init__(
        self,
        max_position_size_pct: float = 20.0,
        max_loss_per_position_pct: float = 10.0,
        max_holding_duration_hours: float = 720.0,
        max_single_stock_pct: float = 15.0,
    ) -> None:
        self._max_position_size_pct = max_position_size_pct
        self._max_loss_per_position_pct = max_loss_per_position_pct
        self._max_holding_duration_hours = max_holding_duration_hours
        self._max_single_stock_pct = max_single_stock_pct
        self._positions: dict[str, PositionInfo] = {}
        self._alerts: list[PositionAlert] = []
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the position monitor."""
        self._initialized = True
        logger.info("PositionMonitor initialized.")

    async def stop(self) -> None:
        """Stop the position monitor."""
        self._initialized = False
        logger.info("PositionMonitor stopped.")

    # ---- Core API ----

    async def evaluate_position(
        self,
        symbol: str,
        quantity: float,
        avg_cost: float,
        market_price: float,
        total_equity: float,
        side: str = "LONG",
        asset_class: str = "EQUITY",
        sector: str = "",
        opened_at: Optional[datetime] = None,
    ) -> list[PositionAlert]:
        """
        Evaluate a single position against all limits.

        Returns a list of PositionAlert objects for any breached limits.
        """
        async with self._lock:
            market_value = abs(quantity) * market_price
            unrealized_pnl = quantity * (market_price - avg_cost)
            pnl_pct = ((market_price - avg_cost) / abs(avg_cost)) * 100 if avg_cost != 0 else 0.0
            weight_pct = (market_value / total_equity) * 100 if total_equity > 0 else 0.0

            # Holding duration
            duration = 0.0
            if opened_at:
                duration = (datetime.now(timezone.utc) - opened_at).total_seconds() / 3600.0

            info = PositionInfo(
                symbol=symbol,
                quantity=quantity,
                avg_cost=avg_cost,
                market_price=market_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                pnl_pct=pnl_pct,
                weight_pct=weight_pct,
                holding_duration_hours=duration,
                side=side.upper(),
                asset_class=asset_class,
                sector=sector,
                opened_at=opened_at,
            )
            self._positions[symbol] = info

        alerts = self._check_limits(info, total_equity)
        return alerts

    async def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """Get position information for a symbol."""
        return self._positions.get(symbol)

    async def get_all_positions(self) -> dict[str, PositionInfo]:
        """Get all tracked positions."""
        return dict(self._positions)

    async def get_alerts(self) -> list[PositionAlert]:
        """Get all position alerts."""
        return list(self._alerts)

    async def clear_alerts(self) -> None:
        """Clear all position alerts."""
        async with self._lock:
            self._alerts.clear()

    # ---- Internal ----

    def _check_limits(self, info: PositionInfo, total_equity: float) -> list[PositionAlert]:
        """Check all position limits and generate alerts."""
        alerts: list[PositionAlert] = []

        # Size limit
        if info.weight_pct > self._max_position_size_pct:
            alerts.append(PositionAlert(
                symbol=info.symbol,
                alert_type="position_size",
                severity="HIGH",
                message=f"Position {info.symbol} is {info.weight_pct:.1f}% of portfolio (limit: {self._max_position_size_pct:.1f}%)",
                current_value=info.weight_pct,
                limit=self._max_position_size_pct,
            ))

        # Loss limit
        if info.pnl_pct < -self._max_loss_per_position_pct:
            alerts.append(PositionAlert(
                symbol=info.symbol,
                alert_type="loss_limit",
                severity="CRITICAL" if info.pnl_pct < -20 else "HIGH",
                message=f"Position {info.symbol} loss {info.pnl_pct:.1f}% exceeds limit",
                current_value=info.pnl_pct,
                limit=-self._max_loss_per_position_pct,
            ))

        # Duration limit
        if info.holding_duration_hours > self._max_holding_duration_hours:
            alerts.append(PositionAlert(
                symbol=info.symbol,
                alert_type="duration",
                severity="WARNING",
                message=f"Position {info.symbol} held for {info.holding_duration_hours:.0f}h (limit: {self._max_holding_duration_hours:.0f}h)",
                current_value=info.holding_duration_hours,
                limit=self._max_holding_duration_hours,
            ))

        async def _store():
            self._alerts.extend(alerts)

        # Need to run in event loop — defer via asyncio.create_task
        import asyncio
        asyncio.get_event_loop().create_task(_store())

        return alerts

    async def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        async with self._lock:
            return {
                "tracked_positions": len(self._positions),
                "alerts": len(self._alerts),
                "position_weights": {
                    s: p.weight_pct for s, p in self._positions.items()
                },
            }

    async def health_check(self) -> dict[str, Any]:
        """Check monitor health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "tracked_positions": len(self._positions),
        }
