"""RecoveryMetrics — recovery operation metrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class RecoveryMetrics:
    """Metrics for recovery operations."""

    recovery_total: int = 0
    recovery_success_total: int = 0
    recovery_failure_total: int = 0
    recovery_latency_sum: float = 0.0
    recovery_latency_count: int = 0

    dead_letter_total: int = 0
    dead_letter_resolved_total: int = 0
    dead_letter_open: int = 0

    def record_recovery(self, success: bool, latency: float = 0) -> None:
        self.recovery_total += 1
        if success:
            self.recovery_success_total += 1
        else:
            self.recovery_failure_total += 1
        self.recovery_latency_sum += latency
        self.recovery_latency_count += 1

    def record_dead_letter_added(self) -> None:
        self.dead_letter_total += 1
        self.dead_letter_open += 1

    def record_dead_letter_resolved(self) -> None:
        self.dead_letter_resolved_total += 1
        self.dead_letter_open = max(0, self.dead_letter_open - 1)

    @property
    def recovery_success_rate(self) -> float:
        if self.recovery_total == 0:
            return 0.0
        return self.recovery_success_total / self.recovery_total

    @property
    def avg_recovery_latency(self) -> float:
        if self.recovery_latency_count == 0:
            return 0.0
        return self.recovery_latency_sum / self.recovery_latency_count

    def to_dict(self) -> Dict:
        return {
            "recovery_total": self.recovery_total,
            "recovery_success_total": self.recovery_success_total,
            "recovery_failure_total": self.recovery_failure_total,
            "recovery_success_rate": self.recovery_success_rate,
            "avg_recovery_latency": self.avg_recovery_latency,
            "dead_letter_total": self.dead_letter_total,
            "dead_letter_resolved_total": self.dead_letter_resolved_total,
            "dead_letter_open": self.dead_letter_open,
        }
