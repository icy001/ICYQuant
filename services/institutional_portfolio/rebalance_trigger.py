"""
Rebalance Trigger — Multi-Condition Rebalance Trigger System

Monitors multiple trigger conditions:
    TIME_TRIGGER, DRIFT_TRIGGER, RISK_TRIGGER, REGIME_TRIGGER,
    CAPITAL_TRIGGER, LIQUIDITY_TRIGGER, PERFORMANCE_TRIGGER
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TriggerType(str, Enum):
    TIME = "TIME_TRIGGER"
    DRIFT = "DRIFT_TRIGGER"
    RISK = "RISK_TRIGGER"
    REGIME = "REGIME_TRIGGER"
    CAPITAL = "CAPITAL_TRIGGER"
    LIQUIDITY = "LIQUIDITY_TRIGGER"
    PERFORMANCE = "PERFORMANCE_TRIGGER"


@dataclass
class TriggerState:
    trigger_type: TriggerType
    active: bool = False
    value: float = 0.0
    threshold: float = 0.0
    last_checked: datetime = field(default_factory=datetime.utcnow)


class RebalanceTrigger:
    """
    Monitors multiple trigger conditions for rebalancing.

    Any single active trigger can initiate a rebalance evaluation.
    Multiple triggers increase urgency.
    """

    def __init__(
        self,
        trigger_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.trigger_id = trigger_id or f"rt-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._triggers: Dict[TriggerType, TriggerState] = {
            t: TriggerState(trigger_type=t) for t in TriggerType
        }
        self._thresholds = {
            TriggerType.DRIFT: self.config.get("drift_threshold", 0.02),
            TriggerType.RISK: self.config.get("risk_threshold", 0.03),
            TriggerType.CAPITAL: self.config.get("capital_threshold", 0.10),
            TriggerType.LIQUIDITY: self.config.get("liquidity_threshold", 0.20),
            TriggerType.PERFORMANCE: self.config.get("performance_threshold", 0.10),
        }

    def set_trigger(self, trigger_type: TriggerType, value: float) -> None:
        """Set a trigger value and evaluate if it fires."""
        state = self._triggers[trigger_type]
        state.value = value
        threshold = self._thresholds.get(trigger_type, 0.01)
        state.threshold = threshold
        state.active = abs(value) > threshold
        state.last_checked = datetime.utcnow()

    def check(self) -> bool:
        """Check if ANY trigger is active."""
        return any(s.active for s in self._triggers.values())

    def get_active_triggers(self) -> List[str]:
        """List all active trigger types."""
        return [t.value for t, s in self._triggers.items() if s.active]

    def get_urgency_score(self) -> float:
        """0-1 urgency based on how many triggers are active and how far past threshold."""
        active_count = sum(1 for s in self._triggers.values() if s.active)
        if active_count == 0:
            return 0.0
        avg_excess = 0.0
        count = 0
        for s in self._triggers.values():
            if s.active and s.threshold > 0:
                avg_excess += s.value / s.threshold
                count += 1
        avg_excess = avg_excess / count if count > 0 else 1.0
        return min(1.0, 0.3 + 0.2 * active_count + 0.1 * avg_excess)
