"""
Experiment metrics.

Provides Prometheus-compatible metrics for
monitoring experiment operations.
"""

from __future__ import annotations

from typing import Any, Dict

METRIC_EXPERIMENT_TOTAL = "icyquant_experiment_total"
METRIC_VARIANT_ASSIGNMENT_TOTAL = "icyquant_variant_assignment_total"
METRIC_EXPERIMENT_DURATION_SECONDS = "icyquant_experiment_duration_seconds"


class ExperimentMetrics:
    """Prometheus-compatible metrics for experiments."""

    def __init__(self) -> None:
        self._experiment_total: Dict[str, int] = {}
        self._variant_assignment_total: Dict[str, int] = {}
        self._experiment_durations: Dict[str, float] = {}

    def record_experiment_start(self, experiment_id: str) -> None:
        self._experiment_total[experiment_id] = self._experiment_total.get(experiment_id, 0) + 1

    def record_variant_assignment(
        self,
        experiment_id: str,
        variant_id: str,
    ) -> None:
        key = f"{experiment_id}:{variant_id}"
        self._variant_assignment_total[key] = self._variant_assignment_total.get(key, 0) + 1

    def record_experiment_duration(
        self,
        experiment_id: str,
        duration_seconds: float,
    ) -> None:
        self._experiment_durations[experiment_id] = duration_seconds

    def snapshot(self) -> Dict[str, Any]:
        return {
            "experiment_total": dict(self._experiment_total),
            "variant_assignment_total": dict(self._variant_assignment_total),
            "experiment_durations": dict(self._experiment_durations),
        }

    def get_counter_values(self) -> Dict[str, int]:
        return {
            METRIC_EXPERIMENT_TOTAL: sum(self._experiment_total.values()),
            METRIC_VARIANT_ASSIGNMENT_TOTAL: sum(self._variant_assignment_total.values()),
        }

    def reset(self) -> None:
        self._experiment_total.clear()
        self._variant_assignment_total.clear()
        self._experiment_durations.clear()
