"""StrategyDrawdown — strategy-level drawdown tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.drawdown_engine import (
    DrawdownEngine,
    DrawdownLevel,
    DrawdownState,
)


@dataclass
class StrategyDrawdownProfile:
    """Strategy-level drawdown profile."""

    strategy_id: str
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_value: float = 0.0
    current_value: float = 0.0
    recovery_needed_pct: float = 0.0
    underwater_days: int = 0
    consecutive_loss_days: int = 0
    daily_returns: List[float] = field(default_factory=list)


class StrategyDrawdownTracker:
    """Tracks drawdown at the individual strategy level.

    Includes underwater duration tracking and consecutive loss counting.

    Usage::

        tracker = StrategyDrawdownTracker()
        tracker.update("momentum_strat", 10_500_000)
        profile = tracker.get_profile("momentum_strat")
    """

    def __init__(self, drawdown_engine: Optional[DrawdownEngine] = None):
        self._engine = drawdown_engine or DrawdownEngine()
        self._daily_values: Dict[str, List[tuple[float, float]]] = {}  # (timestamp, value)
        self._underwater_days: Dict[str, int] = {}
        self._consecutive_loss_days: Dict[str, int] = {}

    def update(
        self,
        strategy_id: str,
        current_value: float,
        timestamp: Optional[float] = None,
    ) -> DrawdownState:
        """Update strategy drawdown tracking."""
        import time
        ts = timestamp or time.time()

        # track daily values
        if strategy_id not in self._daily_values:
            self._daily_values[strategy_id] = []
        self._daily_values[strategy_id].append((ts, current_value))

        # update engine
        state = self._engine.update(strategy_id, current_value, DrawdownLevel.STRATEGY, ts)

        # underwater days tracking
        if state.in_drawdown:
            self._underwater_days[strategy_id] = self._underwater_days.get(strategy_id, 0) + 1
        else:
            self._underwater_days[strategy_id] = 0

        # consecutive loss days
        history = self._daily_values[strategy_id]
        if len(history) >= 2:
            prev_val = history[-2][1]
            if current_value < prev_val:
                self._consecutive_loss_days[strategy_id] = (
                    self._consecutive_loss_days.get(strategy_id, 0) + 1
                )
            else:
                self._consecutive_loss_days[strategy_id] = 0

        return state

    def get_profile(self, strategy_id: str) -> StrategyDrawdownProfile:
        """Get drawdown profile for a strategy."""
        state = self._engine.get_state(strategy_id)
        if not state:
            return StrategyDrawdownProfile(strategy_id=strategy_id)

        recovery = self._engine.compute_recovery_needed(strategy_id)

        # daily returns
        history = self._daily_values.get(strategy_id, [])
        daily_rets = []
        for i in range(1, len(history)):
            prev_v = history[i - 1][1]
            curr_v = history[i][1]
            if prev_v > 0:
                daily_rets.append((curr_v - prev_v) / prev_v)

        return StrategyDrawdownProfile(
            strategy_id=strategy_id,
            current_drawdown_pct=state.drawdown_pct,
            max_drawdown_pct=state.max_drawdown_pct,
            peak_value=state.peak_value,
            current_value=state.current_value,
            recovery_needed_pct=recovery,
            underwater_days=self._underwater_days.get(strategy_id, 0),
            consecutive_loss_days=self._consecutive_loss_days.get(strategy_id, 0),
            daily_returns=daily_rets[-100:],  # last 100 days
        )

    def get_critical_strategies(
        self,
        threshold_pct: float = 15.0,
    ) -> List[str]:
        """Get strategies exceeding drawdown threshold."""
        critical = []
        for sid in self._daily_values:
            profile = self.get_profile(sid)
            if profile.current_drawdown_pct >= threshold_pct:
                critical.append(sid)
        return critical

    def reset(self, strategy_id: Optional[str] = None) -> None:
        """Reset tracking."""
        if strategy_id:
            self._daily_values.pop(strategy_id, None)
            self._underwater_days.pop(strategy_id, None)
            self._consecutive_loss_days.pop(strategy_id, None)
        else:
            self._daily_values.clear()
            self._underwater_days.clear()
            self._consecutive_loss_days.clear()
            self._engine.reset()
