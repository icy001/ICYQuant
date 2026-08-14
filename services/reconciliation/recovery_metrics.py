"""Recovery metrics (Commit 40 Part 1.5).

Tracks the effectiveness of the reconciliation engine:

    reconciliation_total / matched / mismatched
    repair_total / success / failed
    recovery_total / success / failed
    manual_review_total

plus derived success rates.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryMetrics:
    reconciliation_total: int = 0
    reconciliation_matched: int = 0
    reconciliation_mismatched: int = 0

    repair_total: int = 0
    repair_success_total: int = 0
    repair_failed_total: int = 0

    recovery_total: int = 0
    recovery_success_total: int = 0
    recovery_failed_total: int = 0

    manual_review_total: int = 0

    def record_reconciliation(self, matched: bool) -> None:
        self.reconciliation_total += 1
        if matched:
            self.reconciliation_matched += 1
        else:
            self.reconciliation_mismatched += 1

    def record_repair(self, success: bool) -> None:
        self.repair_total += 1
        if success:
            self.repair_success_total += 1
        else:
            self.repair_failed_total += 1

    def record_recovery(self, success: bool) -> None:
        self.recovery_total += 1
        if success:
            self.recovery_success_total += 1
        else:
            self.recovery_failed_total += 1

    def record_manual_review(self) -> None:
        self.manual_review_total += 1

    @property
    def repair_success_rate(self) -> float:
        if self.repair_total == 0:
            return 0.0
        return self.repair_success_total / self.repair_total

    @property
    def recovery_success_rate(self) -> float:
        if self.recovery_total == 0:
            return 0.0
        return self.recovery_success_total / self.recovery_total
