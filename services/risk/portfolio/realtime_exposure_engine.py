"""
Real-Time Exposure Engine — Continuous exposure monitoring.

Monitors gross/net/long/short exposure across account, portfolio,
and strategy levels with real-time updates.

Architecture::

    Positions → Gross Exposure → Net Exposure → Long/Short → Asset Exposure
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExposureSnapshot:
    """Point-in-time exposure metrics."""
    account_id: str
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    total_equity: float = 0.0

    # Derived
    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    long_pct: float = 0.0
    short_pct: float = 0.0

    # Breakdown
    by_asset_class: dict[str, float] = field(default_factory=dict)
    by_sector: dict[str, float] = field(default_factory=dict)
    by_currency: dict[str, float] = field(default_factory=dict)
    by_strategy: dict[str, float] = field(default_factory=dict)

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "long_exposure": self.long_exposure,
            "short_exposure": self.short_exposure,
            "total_equity": self.total_equity,
            "gross_leverage": self.gross_leverage,
            "net_leverage": self.net_leverage,
            "long_pct": self.long_pct,
            "short_pct": self.short_pct,
            "by_asset_class": dict(self.by_asset_class),
            "by_sector": dict(self.by_sector),
            "by_currency": dict(self.by_currency),
            "by_strategy": dict(self.by_strategy),
            "timestamp": self.timestamp.isoformat(),
        }


class RealtimeExposureEngine:
    """
    Real-time exposure monitoring engine.

    Tracks gross, net, long, and short exposure across account,
    portfolio, and strategy dimensions. Updates in real-time as
    positions and market prices change.

    Usage::

        engine = RealtimeExposureEngine()
        await engine.initialize()

        await engine.update_position("AAPL", qty=100, price=150, side="LONG", ...)
        exposure = await engine.compute_exposure("ACC-01")
    """

    def __init__(self) -> None:
        self._positions: dict[str, dict[str, Any]] = {}
        self._prices: dict[str, float] = {}
        self._equity: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._update_count: int = 0
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the exposure engine."""
        self._initialized = True
        logger.info("RealtimeExposureEngine initialized.")

    async def stop(self) -> None:
        """Stop the exposure engine."""
        self._initialized = False
        logger.info("RealtimeExposureEngine stopped.")

    # ---- Core API ----

    async def update_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str = "LONG",
        account_id: str = "DEFAULT",
        asset_class: str = "EQUITY",
        sector: str = "",
        currency: str = "USD",
        strategy_id: str = "",
    ) -> None:
        """Update or create a position for exposure tracking."""
        async with self._lock:
            self._positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "side": side.upper(),
                "account_id": account_id,
                "asset_class": asset_class,
                "sector": sector,
                "currency": currency,
                "strategy_id": strategy_id,
            }
            self._prices[symbol] = price
            self._update_count += 1

    async def update_price(self, symbol: str, price: float) -> None:
        """Update market price for a symbol."""
        async with self._lock:
            self._prices[symbol] = price
            if symbol in self._positions:
                self._positions[symbol]["price"] = price
            self._update_count += 1

    async def remove_position(self, symbol: str) -> None:
        """Remove a position from tracking."""
        async with self._lock:
            self._positions.pop(symbol, None)

    async def set_equity(self, account_id: str, equity: float) -> None:
        """Set total equity for an account."""
        self._equity[account_id] = equity

    async def compute_exposure(self, account_id: str) -> ExposureSnapshot:
        """Compute exposure metrics for an account."""
        gross = 0.0
        long_exp = 0.0
        short_exp = 0.0
        by_asset: dict[str, float] = {}
        by_sector: dict[str, float] = {}
        by_currency: dict[str, float] = {}
        by_strategy: dict[str, float] = {}

        async with self._lock:
            for symbol, pos in self._positions.items():
                if pos["account_id"] != account_id:
                    continue

                qty = pos["quantity"]
                price = self._prices.get(symbol, pos["price"])
                mv = abs(qty) * price

                gross += mv
                if qty > 0:
                    long_exp += mv
                else:
                    short_exp += mv

                # Breakdowns
                ac = pos.get("asset_class", "EQUITY")
                by_asset[ac] = by_asset.get(ac, 0.0) + mv

                sec = pos.get("sector", "Other")
                by_sector[sec] = by_sector.get(sec, 0.0) + mv

                cur = pos.get("currency", "USD")
                by_currency[cur] = by_currency.get(cur, 0.0) + mv

                strat = pos.get("strategy_id", "Default")
                by_strategy[strat] = by_strategy.get(strat, 0.0) + mv

        net_exp = long_exp - short_exp
        equity = self._equity.get(account_id, max(gross, 1.0))

        return ExposureSnapshot(
            account_id=account_id,
            gross_exposure=gross,
            net_exposure=net_exp,
            long_exposure=long_exp,
            short_exposure=short_exp,
            total_equity=equity,
            gross_leverage=gross / equity if equity > 0 else 0.0,
            net_leverage=net_exp / equity if equity > 0 else 0.0,
            long_pct=(long_exp / equity * 100) if equity > 0 else 0.0,
            short_pct=(short_exp / equity * 100) if equity > 0 else 0.0,
            by_asset_class=by_asset,
            by_sector=by_sector,
            by_currency=by_currency,
            by_strategy=by_strategy,
        )

    async def get_positions(self, account_id: str = "") -> list[dict[str, Any]]:
        """Get all tracked positions, optionally filtered by account."""
        async with self._lock:
            positions = list(self._positions.values())
            if account_id:
                positions = [p for p in positions if p["account_id"] == account_id]
            return positions

    async def reset(self, account_id: str = "") -> None:
        """Reset exposure tracking, optionally for a specific account."""
        async with self._lock:
            if account_id:
                to_remove = [
                    s for s, p in self._positions.items()
                    if p["account_id"] == account_id
                ]
                for s in to_remove:
                    del self._positions[s]
            else:
                self._positions.clear()
            self._update_count = 0
        logger.info("RealtimeExposureEngine reset.")

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        async with self._lock:
            return {
                "tracked_positions": len(self._positions),
                "tracked_symbols": len(self._prices),
                "updates": self._update_count,
            }

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "tracked_positions": len(self._positions),
            "updates": self._update_count,
        }
