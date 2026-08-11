"""ReconciliationMetrics — reconciliation operation metrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ReconciliationMetrics:
    """Metrics for reconciliation operations."""

    reconciliation_total: int = 0
    reconciliation_consistent_total: int = 0
    reconciliation_mismatch_total: int = 0
    reconciliation_critical_total: int = 0
    reconciliation_latency_sum: float = 0.0
    reconciliation_latency_count: int = 0

    repair_total: int = 0
    repair_auto_total: int = 0
    repair_manual_total: int = 0
    repair_frozen_orders: int = 0

    def record_reconciliation(self, consistent: bool,
                              critical: bool = False,
                              latency: float = 0) -> None:
        self.reconciliation_total += 1
        if consistent:
            self.reconciliation_consistent_total += 1
        else:
            self.reconciliation_mismatch_total += 1
        if critical:
            self.reconciliation_critical_total += 1
        self.reconciliation_latency_sum += latency
        self.reconciliation_latency_count += 1

    def record_repair(self, auto: bool = True) -> None:
        self.repair_total += 1
        if auto:
            self.repair_auto_total += 1
        else:
            self.repair_manual_total += 1

    def record_freeze(self) -> None:
        self.repair_frozen_orders += 1

    def record_unfreeze(self) -> None:
        self.repair_frozen_orders = max(0, self.repair_frozen_orders - 1)

    @property
    def consistency_rate(self) -> float:
        if self.reconciliation_total == 0:
            return 0.0
        return self.reconciliation_consistent_total / self.reconciliation_total

    @property
    def avg_latency(self) -> float:
        if self.reconciliation_latency_count == 0:
            return 0.0
        return self.reconciliation_latency_sum / self.reconciliation_latency_count

    def to_dict(self) -> Dict:
        return {
            "reconciliation_total": self.reconciliation_total,
            "reconciliation_consistent_total": self.reconciliation_consistent_total,
            "reconciliation_mismatch_total": self.reconciliation_mismatch_total,
            "reconciliation_critical_total": self.reconciliation_critical_total,
            "consistency_rate": self.consistency_rate,
            "avg_reconciliation_latency": self.avg_latency,
            "repair_total": self.repair_total,
            "repair_auto_total": self.repair_auto_total,
            "repair_manual_total": self.repair_manual_total,
            "repair_frozen_orders": self.repair_frozen_orders,
        }
