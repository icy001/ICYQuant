"""
Canary release metrics.

Provides Prometheus-compatible metrics for
canary deployment monitoring.
"""

from __future__ import annotations

from typing import Any, Dict

# Metric name constants
METRIC_CANARY_STAGE_TOTAL = "icyquant_canary_stage_total"
METRIC_CANARY_ROLLBACK_TOTAL = "icyquant_canary_rollback_total"
METRIC_CANARY_HEALTH_SCORE = "icyquant_canary_health_score"
METRIC_CANARY_PROMOTION_TOTAL = "icyquant_canary_promotion_total"
METRIC_CANARY_REQUEST_TOTAL = "icyquant_canary_request_total"
METRIC_CANARY_ERROR_TOTAL = "icyquant_canary_error_total"


class CanaryMetrics:
    """
    Prometheus-compatible metrics for canary releases.

    Usage:
        metrics = CanaryMetrics()
        metrics.record_stage("new-risk", 1, 5.0)
        metrics.record_rollback("new-risk", "automatic")
    """

    def __init__(self) -> None:
        """Initialize canary metrics."""
        self._stage_total: Dict[str, int] = {}
        self._rollback_total: Dict[str, int] = {}
        self._health_score: Dict[str, float] = {}
        self._promotion_total: Dict[str, int] = {}
        self._request_total: Dict[str, int] = {}
        self._error_total: Dict[str, int] = {}

    def record_stage(
        self,
        feature_key: str,
        stage_index: int,
        percentage: float,
    ) -> None:
        """Record a stage transition."""
        key = f"{feature_key}:{stage_index}"
        self._stage_total[key] = self._stage_total.get(key, 0) + 1

    def record_rollback(
        self,
        feature_key: str,
        rollback_type: str = "manual",
    ) -> None:
        """Record a rollback."""
        key = f"{feature_key}:{rollback_type}"
        self._rollback_total[key] = self._rollback_total.get(key, 0) + 1

    def record_health_score(
        self,
        feature_key: str,
        score: float,
    ) -> None:
        """Record a health score."""
        self._health_score[feature_key] = score

    def record_promotion(self, feature_key: str) -> None:
        """Record a promotion."""
        self._promotion_total[feature_key] = (
            self._promotion_total.get(feature_key, 0) + 1
        )

    def record_request(
        self,
        feature_key: str,
        error: bool = False,
    ) -> None:
        """Record a request."""
        self._request_total[feature_key] = (
            self._request_total.get(feature_key, 0) + 1
        )
        if error:
            self._error_total[feature_key] = (
                self._error_total.get(feature_key, 0) + 1
            )

    def snapshot(self) -> Dict[str, Any]:
        """Get a full metrics snapshot."""
        return {
            "stage_total": dict(self._stage_total),
            "rollback_total": dict(self._rollback_total),
            "health_score": dict(self._health_score),
            "promotion_total": dict(self._promotion_total),
            "request_total": dict(self._request_total),
            "error_total": dict(self._error_total),
        }

    def get_counter_values(self) -> Dict[str, int]:
        """Get Prometheus counter values."""
        return {
            METRIC_CANARY_STAGE_TOTAL: sum(self._stage_total.values()),
            METRIC_CANARY_ROLLBACK_TOTAL: sum(self._rollback_total.values()),
            METRIC_CANARY_PROMOTION_TOTAL: sum(self._promotion_total.values()),
            METRIC_CANARY_REQUEST_TOTAL: sum(self._request_total.values()),
            METRIC_CANARY_ERROR_TOTAL: sum(self._error_total.values()),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._stage_total.clear()
        self._rollback_total.clear()
        self._health_score.clear()
        self._promotion_total.clear()
        self._request_total.clear()
        self._error_total.clear()
