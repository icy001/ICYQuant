"""Allocation Feedback — closes the loop between prediction and realized outcome.

Records:
- Expected Alpha vs Realized Alpha
- Expected Risk vs Realized Risk
- Expected Impact vs Realized Impact
- Expected Slippage vs Realized Slippage

Feeds prediction errors back to models for improvement.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class FeedbackMetric(str, Enum):
    """Metrics tracked in the feedback loop."""
    ALPHA = "alpha"
    RISK = "risk"
    IMPACT = "impact"
    SLIPPAGE = "slippage"
    COST = "cost"
    LIQUIDITY = "liquidity"
    CAPACITY = "capacity"
    STRESS = "stress"
    SURVIVAL = "survival"
    ALLOCATION_SCORE = "allocation_score"


@dataclass
class PredictionRecord:
    """A single prediction-vs-realized record."""
    metric: FeedbackMetric
    predicted: float = 0.0
    realized: float = 0.0
    error: float = 0.0
    error_pct: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        self.error = self.realized - self.predicted
        if self.predicted != 0:
            self.error_pct = self.error / abs(self.predicted)


@dataclass
class FeedbackReport:
    """Complete feedback report for an allocation execution."""
    strategy_id: str
    decision_id: str = ""
    records: List[PredictionRecord] = field(default_factory=list)
    total_absolute_error: float = 0.0
    mean_error_pct: float = 0.0
    worst_metric: str = ""
    worst_error_pct: float = 0.0
    model_calibration_score: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    requires_model_update: bool = False

    def summarize(self) -> str:
        lines = [
            f"FeedbackReport[{self.strategy_id}]",
            f"  Mean Error: {self.mean_error_pct:.2%}",
            f"  Worst: {self.worst_metric} ({self.worst_error_pct:.2%})",
            f"  Calibration: {self.model_calibration_score:.3f}",
        ]
        for r in self.records:
            lines.append(
                f"  {r.metric.value}: pred={r.predicted:.4f} actual={r.realized:.4f} "
                f"(err={r.error:+.4f}, {r.error_pct:+.1%})"
            )
        return "\n".join(lines)


class AllocationFeedback:
    """Collects and processes allocation feedback.

    Closes the loop: Prediction → Allocation → Execution → Outcome → Error → Adjustment
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._history: List[FeedbackReport] = []
        self._error_threshold = self._config.get("error_threshold", 0.30)
        self._max_history = self._config.get("max_history", 1000)

    def record_feedback(self, strategy_id: str, decision_id: str,
                        predictions: Dict[str, float],
                        realized: Dict[str, float]) -> FeedbackReport:
        """Record feedback by comparing predictions to realized values."""
        report = FeedbackReport(strategy_id=strategy_id, decision_id=decision_id)

        for metric_name in FeedbackMetric:
            pred = predictions.get(metric_name.value, predictions.get(metric_name.name, 0.0))
            actual = realized.get(metric_name.value, realized.get(metric_name.name, 0.0))

            record = PredictionRecord(metric=metric_name, predicted=pred, realized=actual)
            report.records.append(record)

        # Aggregate
        total_abs = sum(abs(r.error) for r in report.records)
        mean_pct = sum(abs(r.error_pct) for r in report.records) / max(1, len(report.records))
        report.total_absolute_error = total_abs
        report.mean_error_pct = mean_pct

        # Worst metric
        worst = max(report.records, key=lambda r: abs(r.error_pct))
        report.worst_metric = worst.metric.value
        report.worst_error_pct = worst.error_pct

        # Calibration: closer to 1 = better
        report.model_calibration_score = max(0.0, 1.0 - report.mean_error_pct)

        # Flag for model update if errors exceed threshold
        report.requires_model_update = report.mean_error_pct > self._error_threshold

        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return report

    def get_model_adjustments(self) -> Dict[str, float]:
        """Get suggested model adjustments based on recent feedback.

        Returns scaling factors for: impact model, capacity model, alpha model.
        """
        if not self._history:
            return {}

        recent = self._history[-100:]
        adjustments = {}

        # Impact model adjustment
        impact_errors = []
        for report in recent:
            for record in report.records:
                if record.metric == FeedbackMetric.IMPACT:
                    impact_errors.append(record.error_pct)

        if impact_errors:
            avg_impact_error = sum(impact_errors) / len(impact_errors)
            # If consistently over-estimating impact, scale down
            adjustments["impact_scale"] = 1.0 - avg_impact_error * 0.5

        # Alpha model bias
        alpha_errors = []
        for report in recent:
            for record in report.records:
                if record.metric == FeedbackMetric.ALPHA:
                    alpha_errors.append(record.error)

        if alpha_errors:
            avg_alpha_bias = sum(alpha_errors) / len(alpha_errors)
            adjustments["alpha_bias_correction"] = -avg_alpha_bias

        return adjustments

    def recent_reports(self, n: int = 10) -> List[FeedbackReport]:
        """Get recent feedback reports."""
        return self._history[-n:]

    def clear_history(self) -> None:
        """Clear feedback history."""
        self._history.clear()
