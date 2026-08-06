"""State metrics — Prometheus-compatible metrics for workflow state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MetricCounter:
    """Simple counter metric (compatible with Prometheus metrics pattern)."""

    name: str
    description: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: int = 0

    def inc(self, amount: int = 1) -> None:
        self._value += amount

    def value(self) -> int:
        return self._value


@dataclass
class MetricGauge:
    """Simple gauge metric."""

    name: str
    description: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0

    def set(self, value: float) -> None:
        self._value = value

    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        self._value -= amount

    def value(self) -> float:
        return self._value


class StateMetricsCollector:
    """Collects and exposes metrics for workflow state operations.

    Metrics:
      - icyquant_workflow_checkpoint_total
      - icyquant_workflow_snapshot_total
      - icyquant_workflow_replay_total
      - icyquant_workflow_recovery_total
      - icyquant_workflow_wal_total
      - icyquant_workflow_idempotent_total
      - icyquant_workflow_transition_total
    """

    def __init__(self):
        self.workflow_checkpoint_total = MetricCounter(
            "icyquant_workflow_checkpoint_total",
            "Total number of checkpoints created",
        )
        self.workflow_snapshot_total = MetricCounter(
            "icyquant_workflow_snapshot_total",
            "Total number of snapshots created",
        )
        self.workflow_replay_total = MetricCounter(
            "icyquant_workflow_replay_total",
            "Total number of workflow replays executed",
        )
        self.workflow_recovery_total = MetricCounter(
            "icyquant_workflow_recovery_total",
            "Total number of recovery operations performed",
        )
        self.workflow_wal_total = MetricCounter(
            "icyquant_workflow_wal_total",
            "Total number of WAL entries written",
        )
        self.workflow_idempotent_total = MetricCounter(
            "icyquant_workflow_idempotent_total",
            "Total number of idempotent operations detected",
        )
        self.workflow_transition_total = MetricCounter(
            "icyquant_workflow_transition_total",
            "Total number of state transitions",
        )

        self.active_workflows = MetricGauge(
            "icyquant_workflow_state_active",
            "Number of active workflow instances",
        )
        self.recovery_duration_seconds = MetricGauge(
            "icyquant_workflow_recovery_duration_seconds",
            "Duration of the last recovery operation",
        )

    def record_checkpoint(self) -> None:
        self.workflow_checkpoint_total.inc()

    def record_snapshot(self) -> None:
        self.workflow_snapshot_total.inc()

    def record_replay(self) -> None:
        self.workflow_replay_total.inc()

    def record_recovery(self) -> None:
        self.workflow_recovery_total.inc()

    def record_wal(self) -> None:
        self.workflow_wal_total.inc()

    def record_idempotent_hit(self) -> None:
        self.workflow_idempotent_total.inc()

    def record_transition(self) -> None:
        self.workflow_transition_total.inc()

    def set_active_count(self, count: int) -> None:
        self.active_workflows.set(float(count))

    def set_recovery_duration(self, seconds: float) -> None:
        self.recovery_duration_seconds.set(seconds)

    def get_all_metrics(self) -> Dict[str, Any]:
        """Return all metrics as a dict for API exposure."""
        return {
            "workflow_checkpoint_total": self.workflow_checkpoint_total.value(),
            "workflow_snapshot_total": self.workflow_snapshot_total.value(),
            "workflow_replay_total": self.workflow_replay_total.value(),
            "workflow_recovery_total": self.workflow_recovery_total.value(),
            "workflow_wal_total": self.workflow_wal_total.value(),
            "workflow_idempotent_total": self.workflow_idempotent_total.value(),
            "workflow_transition_total": self.workflow_transition_total.value(),
            "active_workflows": self.active_workflows.value(),
            "recovery_duration_seconds": self.recovery_duration_seconds.value(),
        }
