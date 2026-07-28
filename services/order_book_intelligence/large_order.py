"""Large Order Tracker — institutional block order & sweep detection.

Monitors large trades, sweep orders, and aggressive execution patterns
to infer institutional activity in real time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OrderCategory(str, Enum):
    """Large order category."""

    INSTITUTIONAL_BLOCK = "institutional_block"  # Single large trade
    SWEEP = "sweep"  # Aggressive sweep across multiple levels
    AGGRESSIVE_BUY = "aggressive_buy"  # Buying at ask repeatedly
    AGGRESSIVE_SELL = "aggressive_sell"  # Selling at bid repeatedly
    ACCUMULATION = "accumulation"  # Gradual buying over time
    DISTRIBUTION = "distribution"  # Gradual selling over time


class ActivityLevel(str, Enum):
    """Institutional activity intensity."""

    LOW = "low"  # Normal retail flow
    MODERATE = "moderate"  # Some institutional activity
    HIGH = "high"  # Significant institutional flow
    EXTREME = "extreme"  # Dominated by institutions


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class LargeOrder:
    """A detected large order or institutional trade.

    Attributes:
        order_id: Unique identifier for this order.
        category: Type of large order.
        price: Execution price or price range.
        total_volume: Total estimated volume.
        executed_volume: Volume already executed.
        remaining_volume: Volume still to execute.
        vwap: Volume-weighted average execution price.
        levels_consumed: Number of book levels consumed (sweeps).
        start_time: When first detected.
        last_update: Last activity time.
        is_active: Whether order is still active.
    """

    order_id: str
    category: OrderCategory
    price: float
    total_volume: float
    executed_volume: float = 0.0
    remaining_volume: float = 0.0
    vwap: float = 0.0
    levels_consumed: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    @property
    def completion_pct(self) -> float:
        """Percentage of order completed."""
        if self.total_volume == 0:
            return 0.0
        return self.executed_volume / self.total_volume

    @property
    def is_sweep(self) -> bool:
        """Whether this is a sweep order."""
        return self.category == OrderCategory.SWEEP

    @property
    def is_aggressive(self) -> bool:
        """Whether this is an aggressive order."""
        return self.category in (
            OrderCategory.AGGRESSIVE_BUY,
            OrderCategory.AGGRESSIVE_SELL,
            OrderCategory.SWEEP,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "order_id": self.order_id,
            "category": self.category.value,
            "price": self.price,
            "total_volume": round(self.total_volume, 2),
            "executed_volume": round(self.executed_volume, 2),
            "completion_pct": round(self.completion_pct, 4),
            "vwap": round(self.vwap, 4),
            "levels_consumed": self.levels_consumed,
            "is_active": self.is_active,
        }


@dataclass
class InstitutionActivity:
    """Aggregated institutional activity report.

    Attributes:
        large_orders: List of detected large orders.
        activity_level: Overall institutional activity level.
        activity_score: Normalized activity score (0–1).
        buy_volume: Total institutional buy volume.
        sell_volume: Total institutional sell volume.
        net_flow: Net institutional flow (buy - sell).
        sweep_count: Number of sweep orders.
        accumulation_score: Accumulation vs distribution signal.
        timestamp: Report time.
    """

    large_orders: list[LargeOrder]
    activity_level: ActivityLevel = ActivityLevel.LOW
    activity_score: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    net_flow: float = 0.0
    sweep_count: int = 0
    accumulation_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def active_orders(self) -> list[LargeOrder]:
        """Currently active large orders."""
        return [o for o in self.large_orders if o.is_active]

    @property
    def buy_pressure(self) -> bool:
        """Whether there is net institutional buying."""
        return self.net_flow > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "activity_level": self.activity_level.value,
            "activity_score": round(self.activity_score, 4),
            "active_order_count": len(self.active_orders),
            "total_orders": len(self.large_orders),
            "buy_volume": round(self.buy_volume, 2),
            "sell_volume": round(self.sell_volume, 2),
            "net_flow": round(self.net_flow, 2),
            "sweep_count": self.sweep_count,
            "accumulation_score": round(self.accumulation_score, 4),
            "top_orders": [o.to_dict() for o in self.large_orders[:5]],
        }


# ---------------------------------------------------------------------------
# LargeOrderTracker
# ---------------------------------------------------------------------------


class LargeOrderTracker:
    """Tracks institutional and large orders in real time.

    Detects block trades, sweep orders, aggressive buying/selling,
    and accumulation/distribution patterns from trade and order
    book data.

    Attributes:
        block_threshold: Minimum notional value for block trade detection.
        sweep_threshold: Minimum levels consumed for sweep detection.
        active_orders: Currently tracked large orders.
        completed_orders: Finished/dissolved orders.
        order_counter: Auto-increment order ID counter.
    """

    DEFAULT_BLOCK_THRESHOLD = 100_000.0  # $100k notional minimum
    DEFAULT_SWEEP_LEVELS = 3  # Consume 3+ levels = sweep
    AGGRESSIVE_RATIO_THRESHOLD = 0.7  # >70% at bid/ask = aggressive

    ACTIVITY_SCORE_THRESHOLDS: dict[ActivityLevel, float] = {
        ActivityLevel.LOW: 0.2,
        ActivityLevel.MODERATE: 0.4,
        ActivityLevel.HIGH: 0.7,
        ActivityLevel.EXTREME: 1.0,
    }

    def __init__(
        self,
        block_threshold: float = 100_000.0,
        sweep_levels: int = 3,
    ) -> None:
        """Initialize the large order tracker.

        Args:
            block_threshold: Minimum notional for block trade.
            sweep_levels: Minimum levels consumed for sweep.
        """
        self.block_threshold = block_threshold
        self.sweep_levels = sweep_levels
        self.active_orders: list[LargeOrder] = []
        self.completed_orders: list[LargeOrder] = []
        self.order_counter: int = 0
        self.history: list[InstitutionActivity] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def track(
        self,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """Track a large order or trade.

        Args:
            order: Dict with keys: price, volume, side, levels_consumed,
                   timestamp, aggressor, category (optional).

        Returns:
            Dict with tracking result.
        """
        volume = order.get("volume", 0.0)
        price = order.get("price", 0.0)
        side = order.get("side", "unknown")
        levels_consumed = order.get("levels_consumed", 0)
        notional = volume * price

        # Determine category
        category = self._categorize(order, levels_consumed, notional)

        # Assign or update order
        existing = self._find_existing_order(price, side, category)
        if existing:
            existing.executed_volume += volume
            existing.remaining_volume = max(0.0, existing.total_volume - existing.executed_volume)
            if existing.vwap == 0:
                existing.vwap = price
            else:
                existing.vwap = (
                    existing.vwap * (existing.executed_volume - volume) + price * volume
                ) / existing.executed_volume
            existing.levels_consumed = max(existing.levels_consumed, levels_consumed)
            existing.last_update = datetime.utcnow()
            tracked = existing
        else:
            self.order_counter += 1
            new_order = LargeOrder(
                order_id=f"LO-{self.order_counter:06d}",
                category=category,
                price=price,
                total_volume=volume * 2,  # rough estimate
                executed_volume=volume,
                remaining_volume=volume,
                vwap=price,
                levels_consumed=levels_consumed,
            )
            self.active_orders.append(new_order)
            tracked = new_order

        # Check completion
        if tracked.completion_pct >= 0.95:
            tracked.is_active = False
            self.active_orders = [o for o in self.active_orders if o.order_id != tracked.order_id]
            self.completed_orders.append(tracked)

        return {
            "order_id": tracked.order_id,
            "category": tracked.category.value,
            "institution": tracked.category in (
                OrderCategory.INSTITUTIONAL_BLOCK,
                OrderCategory.SWEEP,
            ),
            "is_active": tracked.is_active,
            "executed_volume": round(tracked.executed_volume, 2),
            "completion_pct": round(tracked.completion_pct, 4),
        }

    def analyze_activity(self) -> InstitutionActivity:
        """Generate institutional activity report from tracked orders.

        Returns:
            InstitutionActivity with activity level and metrics.
        """
        active = [o for o in self.active_orders if o.is_active]

        buy_vol = sum(
            o.executed_volume
            for o in active
            if o.category in (OrderCategory.AGGRESSIVE_BUY, OrderCategory.ACCUMULATION, OrderCategory.SWEEP)
        )
        sell_vol = sum(
            o.executed_volume
            for o in active
            if o.category in (OrderCategory.AGGRESSIVE_SELL, OrderCategory.DISTRIBUTION)
        )
        net_flow = buy_vol - sell_vol
        total_vol = buy_vol + sell_vol

        sweep_count = sum(1 for o in active if o.is_sweep)
        block_count = sum(1 for o in active if o.category == OrderCategory.INSTITUTIONAL_BLOCK)

        # Activity score: based on order count × size
        activity_score = min(1.0, (len(active) * 0.1 + (total_vol / 1_000_000) * 0.5))

        # Classify level
        level = ActivityLevel.LOW
        for lvl, threshold in sorted(
            self.ACTIVITY_SCORE_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if activity_score >= threshold:
                level = lvl
                break

        # Accumulation score: net buy flow normalized
        accumulation = net_flow / max(total_vol, 1) if total_vol > 0 else 0.0

        report = InstitutionActivity(
            large_orders=list(active),
            activity_level=level,
            activity_score=activity_score,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            net_flow=net_flow,
            sweep_count=sweep_count,
            accumulation_score=accumulation,
        )

        self.history.append(report)
        return report

    # ------------------------------------------------------------------
    # Categorization
    # ------------------------------------------------------------------

    def _categorize(
        self,
        order: dict[str, Any],
        levels_consumed: int,
        notional: float,
    ) -> OrderCategory:
        """Categorize an order/trade."""
        # Explicit category override
        if "category" in order:
            try:
                return OrderCategory(order["category"])
            except ValueError:
                pass

        # Sweep: consumed multiple levels aggressively
        if levels_consumed >= self.sweep_levels:
            if order.get("aggressor", "") == "buy":
                return OrderCategory.SWEEP
            else:
                # Multi-level sell is also a sweep
                side = order.get("side", "")
                if side == "ask":
                    return OrderCategory.SWEEP

        # Aggressive buy/sell (check before block to preserve direction)
        aggressor = order.get("aggressor", "")
        if aggressor == "buy":
            return OrderCategory.AGGRESSIVE_BUY
        elif aggressor == "sell":
            return OrderCategory.AGGRESSIVE_SELL

        # Block: very large notional (no explicit aggressor)
        if notional >= self.block_threshold:
            return OrderCategory.INSTITUTIONAL_BLOCK

        # Default: accumulation if buy side, distribution if sell
        side = order.get("side", "")
        if side in ("bid", "buy"):
            return OrderCategory.ACCUMULATION
        else:
            return OrderCategory.DISTRIBUTION

    def _find_existing_order(
        self,
        price: float,
        side: str,
        category: OrderCategory,
    ) -> Optional[LargeOrder]:
        """Find matching active order for aggregation."""
        for order in self.active_orders:
            if not order.is_active:
                continue
            if order.category != category:
                continue
            # Price proximity check (±1%)
            if price > 0 and abs(order.price - price) / price < 0.01:
                return order
        return None

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_track(
        self,
        price: float,
        volume: float,
        side: str = "bid",
    ) -> dict[str, Any]:
        """Quick order tracking with minimal input.

        Args:
            price: Order price.
            volume: Order volume.
            side: "bid" or "ask".

        Returns:
            Dict with tracking result.
        """
        return self.track({
            "price": price,
            "volume": volume,
            "side": side,
            "levels_consumed": 0,
        })

    def quick_activity(self) -> dict[str, Any]:
        """Quick institutional activity summary.

        Returns:
            Dict with activity metrics.
        """
        report = self.analyze_activity()
        return {
            "activity_level": report.activity_level.value,
            "activity_score": round(report.activity_score, 4),
            "active_orders": len(report.active_orders),
            "net_flow": round(report.net_flow, 2),
            "accumulation_score": round(report.accumulation_score, 4),
        }

    def clear(self) -> None:
        """Reset all tracked orders."""
        self.active_orders.clear()
        self.completed_orders.clear()
        self.order_counter = 0
        self.history.clear()
