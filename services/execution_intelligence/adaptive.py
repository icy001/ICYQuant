from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionPace(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    NORMAL = "NORMAL"
    PASSIVE = "PASSIVE"
    HALT = "HALT"


class MarketRegime(str, Enum):
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
    TRENDING = "TRENDING"
    NEWS_DRIVEN = "NEWS_DRIVEN"
    STRESS = "STRESS"


@dataclass
class ExecutionState:
    order_id: str
    total_qty: int
    filled_qty: int
    remaining_qty: int
    current_pace: ExecutionPace
    elapsed_seconds: float
    avg_execution_price: float
    vwap_benchmark: float
    slippage_bps: float
    market_regime: MarketRegime


@dataclass
class Adjustment:
    previous_pace: ExecutionPace
    new_pace: ExecutionPace
    reason: str
    urgency_change: str = ""
    participation_change: float = 0.0


class AdaptiveExecutionEngine:
    """Adaptive Execution Engine - dynamically adjusts execution based on market conditions."""

    def __init__(self):
        self.current_pace = ExecutionPace.NORMAL
        self.adjustment_history: List[Adjustment] = []
        self.volatility_threshold = 0.02
        self.slippage_alert_threshold_bps = 15.0

    def adjust(self, condition):
        """Adjust execution based on current market conditions.

        Args:
            condition: Market condition data - can be ExecutionState dataclass or dict/symbol.

        Returns:
            Dict containing adjustment decision.
        """
        if isinstance(condition, ExecutionState):
            return self._make_adjustment(condition)
        return {"adjustment": condition}

    def _make_adjustment(self, state: ExecutionState) -> dict:
        new_pace = self._determine_pace(state)
        previous = self.current_pace
        self.current_pace = new_pace

        reason = self._get_adjustment_reason(state, previous, new_pace)

        adjustment = Adjustment(
            previous_pace=previous,
            new_pace=new_pace,
            reason=reason,
            urgency_change="INCREASED" if new_pace == ExecutionPace.AGGRESSIVE else "DECREASED",
        )
        self.adjustment_history.append(adjustment)

        return {
            "adjustment": {
                "order_id": state.order_id,
                "previous_pace": previous.value,
                "new_pace": new_pace.value,
                "reason": reason,
                "remaining_qty": state.remaining_qty,
                "slippage_bps": state.slippage_bps,
                "market_regime": state.market_regime.value,
            }
        }

    def _determine_pace(self, state: ExecutionState) -> ExecutionPace:
        if state.market_regime == MarketRegime.STRESS:
            return ExecutionPace.HALT

        if state.market_regime == MarketRegime.VOLATILE:
            if abs(state.slippage_bps) > self.slippage_alert_threshold_bps:
                return ExecutionPace.PASSIVE
            return ExecutionPace.PASSIVE

        if state.market_regime == MarketRegime.TRENDING:
            if state.slippage_bps < 0:  # Favorable slippage
                return ExecutionPace.AGGRESSIVE
            return ExecutionPace.NORMAL

        if state.market_regime == MarketRegime.NEWS_DRIVEN:
            return ExecutionPace.HALT

        # STABLE market
        return ExecutionPace.NORMAL

    def _get_adjustment_reason(
        self,
        state: ExecutionState,
        previous: ExecutionPace,
        new: ExecutionPace,
    ) -> str:
        if new == ExecutionPace.HALT:
            return f"Halted due to {state.market_regime.value} market conditions"
        if new == ExecutionPace.AGGRESSIVE:
            return "Favorable conditions - increasing execution speed"
        if new == ExecutionPace.PASSIVE:
            return "Adverse conditions - slowing down execution"
        return "Normal market conditions - maintaining pace"

    def should_accelerate(self, state: ExecutionState) -> bool:
        """Check if execution should be accelerated."""
        return (
            state.market_regime == MarketRegime.TRENDING
            and state.slippage_bps < 0
            and state.remaining_qty > 0
        )

    def should_decelerate(self, state: ExecutionState) -> bool:
        """Check if execution should be decelerated."""
        return (
            state.market_regime in (MarketRegime.VOLATILE, MarketRegime.STRESS)
            or abs(state.slippage_bps) > self.slippage_alert_threshold_bps
        )
