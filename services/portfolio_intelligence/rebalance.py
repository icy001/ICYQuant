"""AI Rebalance Engine — intelligent portfolio rebalancing engine.

Determines optimal rebalancing triggers, timing, and trade lists.
Supports threshold-based, calendar-based, tactical, and adaptive
strategies with tax-efficiency and cost optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RebalanceStrategy(str, Enum):
    """Rebalancing strategy types."""

    THRESHOLD_BASED = "threshold_based"  # rebalance when drift exceeds threshold
    CALENDAR_BASED = "calendar_based"  # rebalance on fixed schedule
    TACTICAL = "tactical"  # opportunistic rebalancing
    ADAPTIVE = "adaptive"  # AI-driven rebalancing
    COST_OPTIMIZED = "cost_optimized"  # minimize transaction costs


class RebalanceStatus(str, Enum):
    """Rebalancing decision status."""

    NO_ACTION = "no_action"  # no rebalancing needed
    ACTION_RECOMMENDED = "action_recommended"  # rebalancing suggested
    ACTION_REQUIRED = "action_required"  # rebalancing necessary
    CRITICAL = "critical"  # immediate rebalancing needed


class TradeSide(str, Enum):
    """Trade direction for rebalancing."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class RebalanceTrade:
    """Single trade needed for rebalancing.

    Attributes:
        symbol: Asset symbol.
        side: Buy/sell/hold.
        current_weight: Current portfolio weight.
        target_weight: Target weight after rebalancing.
        trade_weight: Weight to trade (target - current).
        estimated_cost_bps: Estimated transaction cost in basis points.
        priority: Execution priority (1 = highest).
        reason: Reason for this trade.
    """

    symbol: str
    side: TradeSide
    current_weight: float
    target_weight: float
    trade_weight: float = 0.0
    estimated_cost_bps: float = 5.0
    priority: int = 3
    reason: str = ""

    @property
    def trade_weight_abs(self) -> float:
        """Absolute weight to trade."""
        return abs(self.trade_weight)

    @property
    def is_active(self) -> bool:
        """Whether this is an active trade (not hold)."""
        return self.side != TradeSide.HOLD and self.trade_weight_abs > 0.001


@dataclass
class RebalancePlan:
    """Complete rebalancing plan.

    Attributes:
        strategy: Rebalancing strategy used.
        status: Overall rebalancing status.
        trades: List of trades to execute.
        total_turnover: Total portfolio turnover from rebalancing.
        estimated_cost_bps: Total estimated cost in basis points.
        expected_improvement: Expected benefit from rebalancing.
        timestamp: Plan generation time.
        metadata: Additional rebalancing context.
    """

    strategy: RebalanceStrategy
    status: RebalanceStatus = RebalanceStatus.NO_ACTION
    trades: list[RebalanceTrade] = field(default_factory=list)
    total_turnover: float = 0.0
    estimated_cost_bps: float = 0.0
    expected_improvement: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def active_trades(self) -> list[RebalanceTrade]:
        """Only trades that require action."""
        return [t for t in self.trades if t.is_active]

    @property
    def trade_count(self) -> int:
        """Number of active trades."""
        return len(self.active_trades)

    @property
    def buy_count(self) -> int:
        """Number of buy trades."""
        return sum(1 for t in self.active_trades if t.side == TradeSide.BUY)

    @property
    def sell_count(self) -> int:
        """Number of sell trades."""
        return sum(1 for t in self.active_trades if t.side == TradeSide.SELL)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "strategy": self.strategy.value,
            "status": self.status.value,
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side.value,
                    "current_weight": round(t.current_weight, 4),
                    "target_weight": round(t.target_weight, 4),
                    "trade_weight": round(t.trade_weight, 4),
                    "estimated_cost_bps": round(t.estimated_cost_bps, 2),
                }
                for t in self.active_trades
            ],
            "total_turnover": round(self.total_turnover, 4),
            "estimated_cost_bps": round(self.estimated_cost_bps, 2),
            "trade_count": self.trade_count,
        }


# ---------------------------------------------------------------------------
# RebalanceEngine
# ---------------------------------------------------------------------------


class RebalanceEngine:
    """AI-powered portfolio rebalancing engine.

    Monitors drift from target allocations and generates optimal
    rebalancing plans. Supports multiple strategies and considers
    transaction costs, taxes, and market impact.

    Attributes:
        strategy: Default rebalancing strategy.
        drift_threshold: Absolute weight drift that triggers rebalancing (%).
        calendar_frequency_days: Days between calendar rebalancing.
        min_trade_size: Minimum trade weight to consider.
        estimate_cost_bps: Default cost estimate per trade.
        history: Past rebalancing plans.
    """

    DEFAULT_PARAMS: dict[str, Any] = {
        "drift_threshold": 0.05,  # 5% absolute drift triggers rebalance
        "calendar_frequency_days": 90,  # quarterly rebalancing
        "min_trade_size": 0.005,  # 0.5% of portfolio minimum
        "cost_bps": 10.0,  # 10 bps estimated cost per side
        "tax_aware": True,
    }

    def __init__(
        self,
        strategy: RebalanceStrategy = RebalanceStrategy.THRESHOLD_BASED,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the rebalancing engine.

        Args:
            strategy: Default rebalancing strategy.
            params: Override default parameters.
        """
        self.strategy = strategy
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.last_rebalance_date: Optional[datetime] = None
        self.history: list[RebalancePlan] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def plan(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        strategy: Optional[RebalanceStrategy] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RebalancePlan:
        """Generate a rebalancing plan.

        Args:
            current_weights: Current portfolio weights by symbol.
            target_weights: Target portfolio weights by symbol.
            strategy: Override default rebalancing strategy.
            metadata: Optional context (market conditions, costs, taxes).

        Returns:
            RebalancePlan with trades, status, and metrics.
        """
        strategy = strategy or self.strategy
        metadata = metadata or {}

        # Compute drift per symbol
        all_symbols = sorted(set(list(current_weights.keys()) + list(target_weights.keys())))
        drifts = {}
        for s in all_symbols:
            current = current_weights.get(s, 0.0)
            target = target_weights.get(s, 0.0)
            drifts[s] = abs(current - target)

        max_drift = max(drifts.values()) if drifts else 0.0

        # Determine status based on strategy
        if strategy == RebalanceStrategy.THRESHOLD_BASED:
            status = self._evaluate_threshold(max_drift)
        elif strategy == RebalanceStrategy.CALENDAR_BASED:
            status = self._evaluate_calendar(max_drift)
        elif strategy == RebalanceStrategy.TACTICAL:
            status = self._evaluate_tactical(max_drift, metadata)
        elif strategy == RebalanceStrategy.ADAPTIVE:
            status = self._evaluate_adaptive(max_drift, metadata)
        elif strategy == RebalanceStrategy.COST_OPTIMIZED:
            status = self._evaluate_cost_optimized(max_drift, drifts, metadata)
        else:
            status = self._evaluate_threshold(max_drift)

        # Generate trades
        trades = self._generate_trades(all_symbols, current_weights, target_weights)

        # Filter small trades
        min_trade = self.params["min_trade_size"]
        trades = [t for t in trades if t.trade_weight_abs >= min_trade]

        # Skip rebalancing if status is NO_ACTION
        if status == RebalanceStatus.NO_ACTION:
            trades = []

        # Compute total turnover (one-way: sum of buys = sum of sells)
        total_turnover = sum(t.trade_weight_abs for t in trades) / 2.0

        # Estimate total cost
        cost_per_trade = metadata.get("cost_bps", self.params["cost_bps"])
        total_cost = sum(cost_per_trade for t in trades if t.is_active)

        # Expected improvement: reduction in total drift
        improvement = max_drift - (
            max(abs(current_weights.get(s, 0) - target_weights.get(s, 0)) for s in all_symbols)
            if status != RebalanceStatus.NO_ACTION and trades
            else max_drift
        )

        plan = RebalancePlan(
            strategy=strategy,
            status=status,
            trades=trades,
            total_turnover=total_turnover,
            estimated_cost_bps=total_cost,
            expected_improvement=improvement,
            metadata={
                "max_drift": max_drift,
                "drift_per_symbol": {s: round(d, 4) for s, d in drifts.items()},
                **(metadata or {}),
            },
        )

        if status != RebalanceStatus.NO_ACTION:
            self.last_rebalance_date = datetime.utcnow()

        self.history.append(plan)
        return plan

    # ------------------------------------------------------------------
    # Strategy Evaluators
    # ------------------------------------------------------------------

    def _evaluate_threshold(self, max_drift: float) -> RebalanceStatus:
        """Threshold-based evaluation."""
        threshold = self.params["drift_threshold"]
        if max_drift >= threshold * 2.0:
            return RebalanceStatus.CRITICAL
        elif max_drift >= threshold:
            return RebalanceStatus.ACTION_REQUIRED
        elif max_drift >= threshold * 0.8:
            return RebalanceStatus.ACTION_RECOMMENDED
        else:
            return RebalanceStatus.NO_ACTION

    def _evaluate_calendar(self, max_drift: float) -> RebalanceStatus:
        """Calendar-based evaluation with drift overlay."""
        freq = self.params["calendar_frequency_days"]
        days_since = (
            (datetime.utcnow() - self.last_rebalance_date).days
            if self.last_rebalance_date
            else freq + 1
        )

        if days_since >= freq:
            return RebalanceStatus.ACTION_REQUIRED if max_drift > 0.01 else RebalanceStatus.ACTION_RECOMMENDED
        elif max_drift >= self.params["drift_threshold"]:
            return RebalanceStatus.ACTION_RECOMMENDED
        else:
            return RebalanceStatus.NO_ACTION

    def _evaluate_tactical(
        self,
        max_drift: float,
        metadata: dict[str, Any],
    ) -> RebalanceStatus:
        """Tactical rebalancing: market-opportunity driven."""
        market_signal = metadata.get("market_signal", 0.0)  # -1 to +1
        opportunity_threshold = 0.3

        if max_drift >= self.params["drift_threshold"]:
            return RebalanceStatus.ACTION_REQUIRED
        elif abs(market_signal) >= opportunity_threshold and max_drift > 0.02:
            return RebalanceStatus.ACTION_RECOMMENDED
        else:
            return RebalanceStatus.NO_ACTION

    def _evaluate_adaptive(
        self,
        max_drift: float,
        metadata: dict[str, Any],
    ) -> RebalanceStatus:
        """Adaptive rebalancing: combine threshold, volatility, and cost."""
        vol_regime = metadata.get("vol_regime", "normal")
        threshold = self.params["drift_threshold"]

        # Tighten threshold in low vol (easier to rebalance), loosen in high vol
        regime_multipliers = {
            "low_vol": 0.7,
            "normal": 1.0,
            "high_vol": 1.5,
            "crisis": 2.0,
        }
        adjusted_threshold = threshold * regime_multipliers.get(vol_regime, 1.0)

        if max_drift >= adjusted_threshold * 1.5:
            return RebalanceStatus.CRITICAL
        elif max_drift >= adjusted_threshold:
            return RebalanceStatus.ACTION_REQUIRED
        elif max_drift >= adjusted_threshold * 0.7:
            return RebalanceStatus.ACTION_RECOMMENDED
        else:
            return RebalanceStatus.NO_ACTION

    def _evaluate_cost_optimized(
        self,
        max_drift: float,
        drifts: dict[str, float],
        metadata: dict[str, Any],
    ) -> RebalanceStatus:
        """Cost-optimized: only rebalance when benefit > cost."""
        threshold = self.params["drift_threshold"]
        cost = metadata.get("cost_bps", self.params["cost_bps"]) / 10000.0  # bps → fraction

        # Estimated benefit from rebalancing (rough: drift reduction × expected return)
        benefit = max_drift * 0.06  # assume 6% expected return on rebalanced capital

        if max_drift >= threshold and benefit > cost * 2:
            return RebalanceStatus.ACTION_REQUIRED
        elif max_drift >= threshold * 0.8 and benefit > cost:
            return RebalanceStatus.ACTION_RECOMMENDED
        else:
            return RebalanceStatus.NO_ACTION

    # ------------------------------------------------------------------
    # Trade Generation
    # ------------------------------------------------------------------

    def _generate_trades(
        self,
        symbols: list[str],
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> list[RebalanceTrade]:
        """Generate per-symbol rebalancing trades."""
        trades = []
        for i, s in enumerate(symbols):
            current = current_weights.get(s, 0.0)
            target = target_weights.get(s, 0.0)
            trade_w = target - current
            abs_trade = abs(trade_w)

            if abs_trade < 0.0001:
                side = TradeSide.HOLD
            elif trade_w > 0:
                side = TradeSide.BUY
            else:
                side = TradeSide.SELL

            # Priority: larger trades first
            if abs_trade >= 0.05:
                priority = 1
            elif abs_trade >= 0.02:
                priority = 2
            else:
                priority = 3

            trades.append(
                RebalanceTrade(
                    symbol=s,
                    side=side,
                    current_weight=current,
                    target_weight=target,
                    trade_weight=trade_w,
                    estimated_cost_bps=self.params["cost_bps"],
                    priority=priority,
                    reason=f"Drift from {current:.3%} to {target:.3%}",
                )
            )

        # Sort: sells first (to raise cash), then buys, by descending size
        trades.sort(
            key=lambda t: (
                0 if t.side == TradeSide.SELL else 1,
                -t.trade_weight_abs,
            )
        )

        return trades

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_rebalance(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> dict[str, Any]:
        """Quick rebalancing check and plan.

        Args:
            current_weights: Current portfolio weights.
            target_weights: Target portfolio weights.

        Returns:
            Dict with status, trades, and summary.
        """
        plan = self.plan(current_weights, target_weights)
        return {
            "strategy": plan.strategy.value,
            "status": plan.status.value,
            "trade_count": plan.trade_count,
            "buy_count": plan.buy_count,
            "sell_count": plan.sell_count,
            "total_turnover": round(plan.total_turnover, 4),
            "estimated_cost_bps": round(plan.estimated_cost_bps, 2),
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side.value,
                    "from_pct": round(t.current_weight, 4),
                    "to_pct": round(t.target_weight, 4),
                }
                for t in plan.active_trades
            ],
        }

    def last_result(self) -> Optional[RebalancePlan]:
        """Return the most recent rebalancing plan."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset rebalancing history."""
        self.history.clear()
        self.last_rebalance_date = None
