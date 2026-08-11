"""Strategy Rotation — automated strategy rotation based on score changes.

When Strategy A's scores deteriorate and Strategy B's improve,
capital can be rotated from A → B.

Built-in hysteresis prevents excessive rotation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RotationDecision(str, Enum):
    """Rotation decision type."""
    ROTATE_IN = "ROTATE_IN"
    ROTATE_OUT = "ROTATE_OUT"
    HOLD = "HOLD"
    NO_ACTION = "NO_ACTION"


@dataclass
class RotationSignal:
    """Signal indicating a strategy should be rotated in/out."""
    strategy_id: str
    decision: RotationDecision = RotationDecision.NO_ACTION
    current_score: float = 0.0
    previous_score: float = 0.0
    score_change: float = 0.0
    rotation_score: float = 0.0  # Higher = stronger rotation signal
    min_holding_period_satisfied: bool = True
    entry_threshold_met: bool = False
    exit_threshold_met: bool = False
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RotationPlan:
    """Complete strategy rotation plan."""
    rotate_out: List[RotationSignal] = field(default_factory=list)
    rotate_in: List[RotationSignal] = field(default_factory=list)
    hold: List[RotationSignal] = field(default_factory=list)
    total_rotate_out_capital: float = 0.0
    total_rotate_in_capital: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        lines = ["Strategy Rotation Plan:"]
        for s in self.rotate_out:
            lines.append(f"  OUT: {s.strategy_id} (score {s.previous_score:.3f}→{s.current_score:.3f})")
        for s in self.rotate_in:
            lines.append(f"  IN:  {s.strategy_id} (score {s.previous_score:.3f}→{s.current_score:.3f})")
        return "\n".join(lines)


class StrategyRotation:
    """Manages automated strategy rotation with hysteresis.

    Rotation triggers when:
    - Strategy A: scores decline persistently below exit threshold
    - Strategy B: scores rise persistently above entry threshold
    - Minimum holding period has elapsed

    Hysteresis prevents:
      A > B → rotate → A < B → rotate back → A > B → ...
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._entry_threshold = self._config.get("entry_threshold", 0.10)
        self._exit_threshold = self._config.get("exit_threshold", 0.08)
        self._min_holding_days = self._config.get("min_holding_days", 5)
        self._hysteresis_band = self._config.get("hysteresis_band", 0.03)
        self._strategy_entry_time: Dict[str, datetime] = {}
        self._last_rotation: Dict[str, datetime] = {}

    def register_entry(self, strategy_id: str) -> None:
        """Register when a strategy entered the portfolio."""
        self._strategy_entry_time[strategy_id] = datetime.utcnow()

    def evaluate(self, strategy_id: str,
                 current_score: float,
                 previous_score: float,
                 is_active: bool = True,
                 capital: float = 0.0) -> RotationSignal:
        """Evaluate if a strategy should be rotated in/out."""
        score_change = current_score - previous_score
        entry_time = self._strategy_entry_time.get(strategy_id)

        # Check minimum holding period
        min_holding_met = True
        if entry_time:
            days_held = (datetime.utcnow() - entry_time).total_seconds() / 86400
            min_holding_met = days_held >= self._min_holding_days

        signal = RotationSignal(
            strategy_id=strategy_id,
            current_score=current_score,
            previous_score=previous_score,
            score_change=score_change,
            rotation_score=abs(score_change),
            min_holding_period_satisfied=min_holding_met,
        )

        if is_active:
            # Currently active — check if should exit
            if (current_score < (1.0 - self._exit_threshold) and
                score_change < -self._hysteresis_band and
                min_holding_met):
                signal.decision = RotationDecision.ROTATE_OUT
                signal.exit_threshold_met = True
                signal.reason = (
                    f"Score declined {score_change:+.3f}, "
                    f"below exit threshold {self._exit_threshold:.2f}"
                )
            elif score_change < 0 and current_score < 0.40:
                # Warning signal but not yet trigger
                signal.decision = RotationDecision.HOLD
                signal.reason = "Deteriorating but above rotation threshold"
            else:
                signal.decision = RotationDecision.HOLD
                signal.reason = "Scores stable or improving"
        else:
            # Not active — check if should enter
            if (current_score > self._entry_threshold and
                score_change > self._hysteresis_band):
                signal.decision = RotationDecision.ROTATE_IN
                signal.entry_threshold_met = True
                signal.reason = (
                    f"Score improving {score_change:+.3f}, "
                    f"above entry threshold {self._entry_threshold:.2f}"
                )
            else:
                signal.decision = RotationDecision.NO_ACTION
                signal.reason = "Below entry threshold or insufficient improvement"

        return signal

    def create_rotation_plan(self,
                              active_strategies: Dict[str, Dict[str, float]],
                              candidate_strategies: Dict[str, Dict[str, float]],
                              current_capitals: Dict[str, float]) -> RotationPlan:
        """Create a complete rotation plan."""
        plan = RotationPlan()

        # Evaluate active strategies for exit
        for sid, scores in active_strategies.items():
            sig = self.evaluate(
                strategy_id=sid,
                current_score=scores.get("composite_score", 0.5),
                previous_score=scores.get("previous_score", 0.5),
                is_active=True,
                capital=current_capitals.get(sid, 0.0),
            )

            if sig.decision == RotationDecision.ROTATE_OUT:
                plan.rotate_out.append(sig)
                plan.total_rotate_out_capital += current_capitals.get(sid, 0.0)
            else:
                plan.hold.append(sig)

        # Evaluate candidates for entry
        for sid, scores in candidate_strategies.items():
            if sid in active_strategies:
                continue
            sig = self.evaluate(
                strategy_id=sid,
                current_score=scores.get("composite_score", 0.5),
                previous_score=scores.get("previous_score", 0.3),
                is_active=False,
            )

            if sig.decision == RotationDecision.ROTATE_IN:
                plan.rotate_in.append(sig)

        plan.total_rotate_in_capital = plan.total_rotate_out_capital
        return plan

    def reset_rotation_state(self, strategy_id: str = None) -> None:
        """Reset rotation tracking state."""
        if strategy_id:
            self._strategy_entry_time.pop(strategy_id, None)
            self._last_rotation.pop(strategy_id, None)
        else:
            self._strategy_entry_time.clear()
            self._last_rotation.clear()
