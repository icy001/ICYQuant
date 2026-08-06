"""Borrow Cost — short position borrow cost model.

Models the cost of borrowing securities for short selling,
including borrow rates, availability, and accrual.

Borrow types::

    Easy to Borrow → Hard to Borrow → Not Borrowable
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BorrowTier(str, Enum):
    """Borrow availability tiers."""

    EASY = "easy"  # < 0.5% annual
    MODERATE = "moderate"  # 0.5% - 3% annual
    HARD = "hard"  # 3% - 10% annual
    EXTREME = "extreme"  # > 10% annual
    UNAVAILABLE = "unavailable"


@dataclass
class BorrowCostRate:
    """Borrow cost for a single symbol."""

    symbol: str = ""
    annual_rate: float = 0.02  # 2% default
    tier: BorrowTier = BorrowTier.MODERATE
    is_available: bool = True
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BorrowCost:
    """Short borrow cost model.

    Calculates the cost of maintaining short positions, including:
    * Daily borrow rate accruals
    * Tiered rate structure by symbol
    * Availability checks

    Usage::

        bc = BorrowCost()
        cost = bc.calculate_daily("000001.SZ", short_value=50000)
        total = bc.calculate_total("000001.SZ", short_value=50000, days=30)
    """

    # Default annual rates by tier
    DEFAULT_RATES: Dict[BorrowTier, float] = {
        BorrowTier.EASY: 0.003,    # 0.3% annual
        BorrowTier.MODERATE: 0.02,  # 2% annual
        BorrowTier.HARD: 0.06,      # 6% annual
        BorrowTier.EXTREME: 0.15,   # 15% annual
        BorrowTier.UNAVAILABLE: 0.0,
    }

    def __init__(self, default_rate: float = 0.02) -> None:
        self._default_rate = default_rate
        self._rates: Dict[str, BorrowCostRate] = {}
        self._total_borrow_cost = 0.0
        self._days_counted = 0

    # ── rate management ────────────────────────────────────────────────────

    def set_rate(
        self,
        symbol: str,
        annual_rate: float,
        tier: Optional[BorrowTier] = None,
        is_available: bool = True,
    ) -> None:
        """Set borrow rate for a specific symbol."""
        if tier is None:
            tier = self._classify_tier(annual_rate)

        self._rates[symbol] = BorrowCostRate(
            symbol=symbol,
            annual_rate=annual_rate,
            tier=tier,
            is_available=is_available,
        )
        logger.info("Borrow rate set for %s: %.2f%% (%s)", symbol, annual_rate * 100, tier.value)

    def get_rate(self, symbol: str) -> BorrowCostRate:
        """Get borrow rate for a symbol (returns default if not set)."""
        if symbol in self._rates:
            return self._rates[symbol]
        return BorrowCostRate(
            symbol=symbol,
            annual_rate=self._default_rate,
            tier=BorrowTier.MODERATE,
        )

    def is_borrowable(self, symbol: str) -> bool:
        """Check if a symbol is available for short selling."""
        rate = self._rates.get(symbol)
        if rate:
            return rate.is_available
        return True  # default: available

    # ── cost calculation ───────────────────────────────────────────────────

    def calculate_daily(
        self,
        symbol: str,
        short_value: float,
        days: int = 1,
    ) -> float:
        """Calculate daily borrow cost for a short position.

        Args:
            symbol: Ticker symbol.
            short_value: Total short position value.
            days: Number of days to calculate for.

        Returns:
            Borrow cost in currency units.
        """
        rate = self.get_rate(symbol)
        if not rate.is_available:
            logger.warning("Symbol %s is not borrowable, cost set to 0", symbol)
            return 0.0

        daily_rate = rate.annual_rate / 365
        cost = short_value * daily_rate * days

        self._total_borrow_cost += cost
        self._days_counted += days

        return cost

    def calculate_total(
        self,
        symbol: str,
        short_value: float,
        days: int,
    ) -> float:
        """Calculate total borrow cost for a given holding period."""
        return self.calculate_daily(symbol, short_value, days)

    def calculate_batch(
        self,
        positions: Dict[str, float],  # symbol → short_value
        days: int = 1,
    ) -> Dict[str, float]:
        """Calculate borrow costs for multiple positions.

        Args:
            positions: Dict of symbol → short value.
            days: Number of days.

        Returns:
            Dict of symbol → borrow cost.
        """
        costs: Dict[str, float] = {}
        for symbol, value in positions.items():
            costs[symbol] = self.calculate_daily(symbol, value, days)
        return costs

    # ── helpers ────────────────────────────────────────────────────────────

    @classmethod
    def _classify_tier(cls, annual_rate: float) -> BorrowTier:
        """Classify an annual rate into a borrow tier."""
        if annual_rate < 0.005:
            return BorrowTier.EASY
        elif annual_rate < 0.03:
            return BorrowTier.MODERATE
        elif annual_rate < 0.10:
            return BorrowTier.HARD
        return BorrowTier.EXTREME

    # ── query ──────────────────────────────────────────────────────────────

    def get_all_rates(self) -> Dict[str, BorrowCostRate]:
        """Get all configured borrow rates."""
        return self._rates.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Return borrow cost statistics."""
        rates = self._rates
        return {
            "configured_symbols": len(rates),
            "default_rate": self._default_rate,
            "total_borrow_cost": self._total_borrow_cost,
            "days_counted": self._days_counted,
            "by_tier": {
                tier.value: sum(1 for r in rates.values() if r.tier == tier)
                for tier in BorrowTier
            },
        }
