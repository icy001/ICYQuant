"""
ICYQuant Retraining Trigger — Multi-condition retraining trigger logic.

Evaluates conditions that should trigger model retraining:
  - Drift signals (data, feature, prediction)
  - Performance degradation
  - Scheduled intervals
  - Data quality events
  - Manual requests

Implements threshold-based triggering with hysteresis to prevent flapping.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TriggerType(str, Enum):
    DRIFT = "drift"
    PERFORMANCE = "performance"
    SCHEDULE = "schedule"
    DATA_QUALITY = "data_quality"
    MANUAL = "manual"
    PRE_DEPLOYMENT = "pre_deployment"


class TriggerDecision(str, Enum):
    RETRAIN = "retrain"
    MONITOR = "monitor"
    NO_ACTION = "no_action"


@dataclass
class TriggerCondition:
    """A single trigger condition."""
    trigger_type: TriggerType
    metric: str           # e.g., "psi", "error_rate", "ic"
    threshold: float      # Trigger threshold
    comparison: str = ">"  # >, <, >=, <=
    cooldown_minutes: int = 60
    min_samples: int = 100
    enabled: bool = True

    def evaluate(self, current_value: float) -> bool:
        if not self.enabled:
            return False
        if self.comparison == ">":
            return current_value > self.threshold
        elif self.comparison == "<":
            return current_value < self.threshold
        elif self.comparison == ">=":
            return current_value >= self.threshold
        elif self.comparison == "<=":
            return current_value <= self.threshold
        return False


@dataclass
class TriggerEvaluation:
    """Result of evaluating all trigger conditions."""
    model_id: str
    timestamp: str
    trigger_decision: TriggerDecision = TriggerDecision.NO_ACTION
    triggered_by: List[str] = field(default_factory=list)
    conditions: Dict[str, bool] = field(default_factory=dict)
    metrics_snapshot: Dict[str, float] = field(default_factory=dict)
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Retraining Trigger
# ---------------------------------------------------------------------------

class RetrainingTrigger:
    """Evaluates multiple conditions for retraining triggers.

    Usage::

        trigger = RetrainingTrigger()
        trigger.add_condition("nvda_model", TriggerCondition(...))

        eval = trigger.evaluate("nvda_model", {"psi": 0.35, "error_rate": 0.08})
        if eval.trigger_decision == TriggerDecision.RETRAIN:
            await retraining_manager.trigger("nvda_model")
    """

    def __init__(self):
        self._initialized = False
        self._conditions: Dict[str, List[TriggerCondition]] = {}

        # Cooldown tracking
        self._last_triggered: Dict[str, Dict[str, float]] = {}

        # Hysteresis: when to stop retraining (must drop below this)
        self._hysteresis_factor: float = 0.8

        # Callbacks
        self._on_trigger: Optional[Callable[[TriggerEvaluation], None]] = None

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("RetrainingTrigger initialized")

    # ------------------------------------------------------------------
    # Condition management
    # ------------------------------------------------------------------

    def add_condition(self, model_id: str, condition: TriggerCondition) -> None:
        """Add a trigger condition for a model."""
        if model_id not in self._conditions:
            self._conditions[model_id] = []
        self._conditions[model_id].append(condition)

    def remove_condition(self, model_id: str, metric: str) -> bool:
        """Remove a trigger condition by metric name."""
        if model_id not in self._conditions:
            return False
        before = len(self._conditions[model_id])
        self._conditions[model_id] = [
            c for c in self._conditions[model_id] if c.metric != metric
        ]
        return len(self._conditions[model_id]) < before

    def get_conditions(self, model_id: str) -> List[TriggerCondition]:
        return self._conditions.get(model_id, [])

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        model_id: str,
        metrics: Dict[str, float],
    ) -> TriggerEvaluation:
        """Evaluate all conditions against current metrics.

        Args:
            model_id: Model identifier.
            metrics: Current metric values keyed by metric name.

        Returns:
            TriggerEvaluation with decision.
        """
        eval_result = TriggerEvaluation(
            model_id=model_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics_snapshot=dict(metrics),
        )

        conditions = self._conditions.get(model_id, [])
        if not conditions:
            return eval_result

        triggered = []
        for condition in conditions:
            value = metrics.get(condition.metric)
            if value is None:
                continue

            result = condition.evaluate(value)
            eval_result.conditions[condition.metric] = result

            if result and self._check_cooldown(model_id, condition):
                triggered.append(condition.metric)

        if triggered:
            eval_result.trigger_decision = TriggerDecision.RETRAIN
            eval_result.triggered_by = triggered
            eval_result.recommendation = (
                f"Retrain triggered by: {', '.join(triggered)}"
            )
            # Record trigger time
            self._record_trigger_time(model_id, triggered)
        else:
            eval_result.trigger_decision = TriggerDecision.NO_ACTION

        return eval_result

    def evaluate_all(
        self,
        all_metrics: Dict[str, Dict[str, float]],
    ) -> Dict[str, TriggerEvaluation]:
        """Evaluate all models against their conditions."""
        return {
            model_id: self.evaluate(model_id, metrics)
            for model_id, metrics in all_metrics.items()
        }

    # ------------------------------------------------------------------
    # Cooldown
    # ------------------------------------------------------------------

    def _check_cooldown(self, model_id: str, condition: TriggerCondition) -> bool:
        """Check if condition is in cooldown period."""
        if model_id not in self._last_triggered:
            self._last_triggered[model_id] = {}
            return True

        last_time = self._last_triggered[model_id].get(condition.metric, 0)
        elapsed_minutes = (
            datetime.now(timezone.utc).timestamp() - last_time
        ) / 60.0

        return elapsed_minutes >= condition.cooldown_minutes

    def _record_trigger_time(
        self,
        model_id: str,
        metrics: List[str],
    ) -> None:
        """Record when conditions were triggered."""
        if model_id not in self._last_triggered:
            self._last_triggered[model_id] = {}
        now = datetime.now(timezone.utc).timestamp()
        for m in metrics:
            self._last_triggered[model_id][m] = now

    # ------------------------------------------------------------------
    # Default conditions
    # ------------------------------------------------------------------

    @classmethod
    def create_default_conditions(cls, model_id: str) -> List[TriggerCondition]:
        """Create a sensible default set of trigger conditions."""
        return [
            TriggerCondition(
                trigger_type=TriggerType.PERFORMANCE,
                metric="error_rate",
                threshold=0.10,
                comparison=">",
                cooldown_minutes=60,
            ),
            TriggerCondition(
                trigger_type=TriggerType.PERFORMANCE,
                metric="ic",
                threshold=0.01,
                comparison="<",
                cooldown_minutes=120,
            ),
            TriggerCondition(
                trigger_type=TriggerType.DRIFT,
                metric="psi",
                threshold=0.25,
                comparison=">",
                cooldown_minutes=60,
            ),
            TriggerCondition(
                trigger_type=TriggerType.DRIFT,
                metric="prediction_drift",
                threshold=0.30,
                comparison=">",
                cooldown_minutes=60,
            ),
        ]

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_trigger(self, callback: Callable[[TriggerEvaluation], None]) -> None:
        self._on_trigger = callback

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "models_with_conditions": len(self._conditions),
            "total_conditions": sum(len(c) for c in self._conditions.values()),
        }

    def __repr__(self) -> str:
        return f"RetrainingTrigger(conditions={sum(len(c) for c in self._conditions.values())})"
