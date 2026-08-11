"""
Model Health — Continuous health monitoring for production models.

Monitors performance, drift, decay, stability, risk, execution quality,
and data quality to compute a Model Health Score.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelHealthScore:
    """Composite health score for a model."""
    model_id: str
    overall: float = 1.0  # 0.0 = dead, 1.0 = perfect
    performance: float = 1.0
    drift: float = 1.0
    decay: float = 1.0
    stability: float = 1.0
    risk: float = 1.0
    execution: float = 1.0
    data_quality: float = 1.0
    status: str = "healthy"  # healthy, warning, degraded, quarantined
    last_checked: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "overall": self.overall,
            "components": {
                "performance": self.performance,
                "drift": self.drift,
                "decay": self.decay,
                "stability": self.stability,
                "risk": self.risk,
                "execution": self.execution,
                "data_quality": self.data_quality,
            },
            "status": self.status,
            "last_checked": self.last_checked,
        }


class ModelHealth:
    """
    Continuous health monitoring for production models.

    Computes a composite health score from multiple dimensions:
    performance, drift, decay, stability, risk, execution, and data quality.
    """

    def __init__(self):
        self._scores: dict[str, ModelHealthScore] = {}
        self._health_history: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # Score Computation
    # ------------------------------------------------------------------

    def compute(
        self,
        model_id: str,
        expected_sharpe: float = 0.0,
        actual_sharpe: float = 0.0,
        drift_measure: float = 0.0,
        decay_rate: float = 0.0,
        stability_score: float = 1.0,
        risk_compliance: float = 1.0,
        execution_score: float = 1.0,
        data_quality_score: float = 1.0,
    ) -> ModelHealthScore:
        """Compute a composite health score."""

        # Performance: ratio of actual to expected
        performance = min(1.0, max(0.0, actual_sharpe / max(expected_sharpe, 0.01)))

        # Drift: invert (higher drift = lower score)
        drift = max(0.0, 1.0 - drift_measure)

        # Decay: invert (higher decay = lower score)
        decay = max(0.0, 1.0 - decay_rate)

        # Composite
        weights = {
            "performance": 0.25,
            "drift": 0.15,
            "decay": 0.15,
            "stability": 0.15,
            "risk": 0.15,
            "execution": 0.10,
            "data_quality": 0.05,
        }

        overall = (
            weights["performance"] * performance +
            weights["drift"] * drift +
            weights["decay"] * decay +
            weights["stability"] * stability_score +
            weights["risk"] * risk_compliance +
            weights["execution"] * execution_score +
            weights["data_quality"] * data_quality_score
        )

        # Status
        if overall >= 0.8:
            status = "healthy"
        elif overall >= 0.6:
            status = "warning"
        elif overall >= 0.4:
            status = "degraded"
        else:
            status = "quarantined"

        score = ModelHealthScore(
            model_id=model_id,
            overall=overall,
            performance=performance,
            drift=drift,
            decay=decay,
            stability=stability_score,
            risk=risk_compliance,
            execution=execution_score,
            data_quality=data_quality_score,
            status=status,
        )

        self._scores[model_id] = score
        self._health_history.setdefault(model_id, []).append(score.to_dict())

        if status in ("degraded", "quarantined"):
            logger.warning("Model %s health: %s (score=%.2f)", model_id, status, overall)

        return score

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, model_id: str) -> Optional[ModelHealthScore]:
        return self._scores.get(model_id)

    def get_status(self, model_id: str) -> str:
        score = self._scores.get(model_id)
        return score.status if score else "unknown"

    def all_healthy(self) -> bool:
        return all(s.status == "healthy" for s in self._scores.values())

    def degraded_models(self) -> list[str]:
        return [mid for mid, s in self._scores.items() if s.status in ("degraded", "quarantined")]

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "models_monitored": len(self._scores),
            "healthy": len([s for s in self._scores.values() if s.status == "healthy"]),
            "warning": len([s for s in self._scores.values() if s.status == "warning"]),
            "degraded": len([s for s in self._scores.values() if s.status == "degraded"]),
            "quarantined": len([s for s in self._scores.values() if s.status == "quarantined"]),
            "average_health": sum(s.overall for s in self._scores.values()) / max(len(self._scores), 1),
        }
