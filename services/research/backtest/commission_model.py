"""Commission Model — broker commission calculation.

Supports various commission structures across different markets
and brokers.

Types::

    Per Share → Per Order → Percentage → Tiered
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CommissionType(str, Enum):
    """Commission calculation types."""

    PER_SHARE = "per_share"
    PER_ORDER = "per_order"
    PERCENTAGE = "percentage"
    TIERED = "tiered"


class CommissionModel:
    """Multi-type broker commission calculator.

    Supports:
    * Per share — fixed cost per share traded
    * Per order — fixed cost per order regardless of size
    * Percentage — percentage of trade notional value
    * Tiered — rate changes based on monthly volume

    Usage::

        model = CommissionModel(CommissionType.PERCENTAGE, rate=0.0003, min_cost=5.0)
        cost = model.calculate(trade_value=50000, quantity=1000)
    """

    def __init__(
        self,
        commission_type: CommissionType = CommissionType.PERCENTAGE,
        rate: float = 0.0003,
        min_cost: float = 5.0,
        max_cost: Optional[float] = None,
        per_share_cost: float = 0.005,
        per_order_cost: float = 5.0,
        tier_thresholds: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        self._type = commission_type
        self._rate = rate
        self._min_cost = min_cost
        self._max_cost = max_cost
        self._per_share_cost = per_share_cost
        self._per_order_cost = per_order_cost
        self._tier_thresholds = tier_thresholds or [
            (100_000, 0.003),   # < 100k: 0.3%
            (500_000, 0.0025),  # 100k-500k: 0.25%
            (1_000_000, 0.002),  # 500k-1M: 0.2%
            (5_000_000, 0.0015),  # 1M-5M: 0.15%
            (float("inf"), 0.001),  # > 5M: 0.1%
        ]
        self._monthly_volume: float = 0.0

        # Tracking
        self._total_trades = 0
        self._total_commission = 0.0

    # ── calculation ────────────────────────────────────────────────────────

    def calculate(
        self,
        trade_value: float,
        quantity: float,
        side: str = "buy",
    ) -> float:
        """Calculate commission for a trade.

        Args:
            trade_value: Total trade notional value.
            quantity: Number of shares/units.
            side: buy or sell.

        Returns:
            Commission cost.
        """
        if self._type == CommissionType.PER_SHARE:
            cost = self._per_share(quantity)

        elif self._type == CommissionType.PER_ORDER:
            cost = self._per_order()

        elif self._type == CommissionType.TIERED:
            cost = self._tiered(trade_value)

        else:  # PERCENTAGE (default)
            cost = self._percentage(trade_value)

        self._total_trades += 1
        self._total_commission += cost
        self._monthly_volume += trade_value

        return cost

    # ── calculation methods ────────────────────────────────────────────────

    def _per_share(self, quantity: float) -> float:
        """Per-share commission."""
        return quantity * self._per_share_cost

    def _per_order(self) -> float:
        """Per-order fixed commission."""
        return self._per_order_cost

    def _percentage(self, trade_value: float) -> float:
        """Percentage-based commission with min/max caps."""
        cost = trade_value * self._rate
        if self._min_cost and cost < self._min_cost:
            cost = self._min_cost
        if self._max_cost and cost > self._max_cost:
            cost = self._max_cost
        return cost

    def _tiered(self, trade_value: float) -> float:
        """Tiered commission based on monthly volume."""
        for threshold, rate in self._tier_thresholds:
            if self._monthly_volume < threshold:
                cost = trade_value * rate
                break
        else:
            cost = trade_value * self._tier_thresholds[-1][1]
        return cost

    # ── configuration ──────────────────────────────────────────────────────

    def set_type(self, commission_type: CommissionType) -> None:
        """Change the commission calculation type."""
        self._type = commission_type
        logger.info("Commission type changed to: %s", commission_type.value)

    def set_params(
        self,
        rate: Optional[float] = None,
        min_cost: Optional[float] = None,
        max_cost: Optional[float] = None,
        per_share_cost: Optional[float] = None,
        per_order_cost: Optional[float] = None,
    ) -> None:
        """Update commission parameters."""
        if rate is not None:
            self._rate = rate
        if min_cost is not None:
            self._min_cost = min_cost
        if max_cost is not None:
            self._max_cost = max_cost
        if per_share_cost is not None:
            self._per_share_cost = per_share_cost
        if per_order_cost is not None:
            self._per_order_cost = per_order_cost

    def reset_monthly_volume(self) -> None:
        """Reset monthly volume counter (for tiered pricing)."""
        self._monthly_volume = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Return commission model statistics."""
        return {
            "type": self._type.value,
            "rate": self._rate,
            "min_cost": self._min_cost,
            "max_cost": self._max_cost,
            "total_commission": self._total_commission,
            "total_trades": self._total_trades,
            "avg_commission": self._total_commission / max(self._total_trades, 1),
            "monthly_volume": self._monthly_volume,
        }
