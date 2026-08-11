"""Rebalance Threshold — determines when rebalancing is triggered.

Built-in hysteresis to prevent excessive trading:
- Entry threshold: triggers rebalance when deviation exceeds
- Exit threshold: rebalance is considered complete when deviation falls below
- Hysteresis band: prevents oscillation around the threshold
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ThresholdMode(str, Enum):
    """Threshold mode."""
    ABSOLUTE = "ABSOLUTE"  # Fixed percentage deviation
    RELATIVE = "RELATIVE"  # Relative to weight
    BAND = "BAND"  # Upper/lower bands
    ADAPTIVE = "ADAPTIVE"  # Adjusts with volatility


@dataclass
class ThresholdConfig:
    """Configuration for rebalance thresholds."""
    entry_threshold: float = 0.02  # Trigger rebalance when |target - current| > this
    exit_threshold: float = 0.005  # Complete rebalance when deviation < this
    absolute_max_deviation: float = 0.10  # Always rebalance beyond this
    min_holding_period_days: int = 1  # Minimum time before re-entering
    hysteresis_band: float = 0.005  # Prevents oscillation
    mode: ThresholdMode = ThresholdMode.ABSOLUTE

    def with_hysteresis(self, entry: float, exit_: float) -> "ThresholdConfig":
        """Create config with hysteresis (different entry/exit thresholds)."""
        return ThresholdConfig(
            entry_threshold=entry,
            exit_threshold=exit_,
            hysteresis_band=abs(entry - exit_),
            mode=self.mode,
        )


@dataclass
class ThresholdResult:
    """Threshold check result for a single strategy."""
    strategy_id: str
    deviation: float = 0.0
    should_rebalance: bool = False
    is_entering: bool = False
    is_exiting: bool = False
    is_complete: bool = True
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RebalanceThreshold:
    """Manages rebalance thresholds with hysteresis.

    Avoids the problem of rapid oscillation:
      A > B → rebalance → A < B → rebalance → A > B → ...
    """

    def __init__(self, config: Optional[ThresholdConfig] = None):
        self._config = config or ThresholdConfig()
        self._last_action: Dict[str, str] = {}  # strategy_id → "enter"/"exit"
        self._last_action_time: Dict[str, datetime] = {}

    def check(self, strategy_id: str,
              current_weight: float,
              target_weight: float,
              total_capital: float = 0.0) -> ThresholdResult:
        """Check if rebalance should be triggered."""
        deviation = abs(target_weight - current_weight)
        cfg = self._config

        # Absolute max always triggers
        if deviation > cfg.absolute_max_deviation:
            return ThresholdResult(
                strategy_id=strategy_id,
                deviation=deviation,
                should_rebalance=True,
                is_entering=True,
                is_complete=False,
                reason=f"Deviation {deviation:.4f} > absolute max {cfg.absolute_max_deviation:.4f}",
            )

        last_action = self._last_action.get(strategy_id)
        last_time = self._last_action_time.get(strategy_id)

        # Check minimum holding period
        if last_time and last_action == "enter":
            days_since = (datetime.utcnow() - last_time).total_seconds() / 86400
            if days_since < cfg.min_holding_period_days:
                return ThresholdResult(
                    strategy_id=strategy_id,
                    deviation=deviation,
                    should_rebalance=False,
                    is_complete=False,
                    reason=f"Min holding period: {days_since:.1f}/{cfg.min_holding_period_days} days",
                )

        # Hysteresis logic
        if deviation > cfg.entry_threshold:
            # Enter rebalance zone
            self._last_action[strategy_id] = "enter"
            self._last_action_time[strategy_id] = datetime.utcnow()
            return ThresholdResult(
                strategy_id=strategy_id,
                deviation=deviation,
                should_rebalance=True,
                is_entering=True,
                is_complete=False,
                reason=f"Deviation {deviation:.4f} > entry {cfg.entry_threshold:.4f}",
            )

        if last_action == "enter" and deviation > cfg.exit_threshold:
            # Still in rebalance, not yet complete
            return ThresholdResult(
                strategy_id=strategy_id,
                deviation=deviation,
                should_rebalance=True,
                is_complete=False,
                reason=f"Rebalance in progress, deviation {deviation:.4f} > exit {cfg.exit_threshold:.4f}",
            )

        # Below exit threshold: complete
        if last_action == "enter":
            self._last_action[strategy_id] = "exit"
            self._last_action_time[strategy_id] = datetime.utcnow()

        return ThresholdResult(
            strategy_id=strategy_id,
            deviation=deviation,
            should_rebalance=False,
            is_complete=True,
            reason=f"Within threshold: {deviation:.4f} ≤ {cfg.entry_threshold:.4f}",
        )

    def batch_check(self, weights: Dict[str, Tuple[float, float]]
                    ) -> List[ThresholdResult]:
        """Check thresholds for multiple strategies.

        Args:
            weights: {strategy_id: (current_weight, target_weight)}
        """
        results = []
        for sid, (current, target) in weights.items():
            results.append(self.check(sid, current, target))
        return results

    def reset(self, strategy_id: str = None) -> None:
        """Reset threshold state."""
        if strategy_id:
            self._last_action.pop(strategy_id, None)
            self._last_action_time.pop(strategy_id, None)
        else:
            self._last_action.clear()
            self._last_action_time.clear()
