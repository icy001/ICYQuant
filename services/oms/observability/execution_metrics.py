"""ExecutionMetrics — execution gateway metrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ExecutionMetrics:
    """Metrics for execution gateway operations."""

    execution_requests_total: int = 0
    execution_ack_total: int = 0
    execution_reject_total: int = 0
    execution_timeout_total: int = 0
    execution_unknown_total: int = 0
    execution_duplicate_total: int = 0
    execution_conflict_total: int = 0

    cancel_requests_total: int = 0
    cancel_confirmed_total: int = 0
    cancel_timeout_total: int = 0

    def record_request(self) -> None:
        self.execution_requests_total += 1

    def record_ack(self) -> None:
        self.execution_ack_total += 1

    def record_reject(self) -> None:
        self.execution_reject_total += 1

    def record_timeout(self) -> None:
        self.execution_timeout_total += 1
        self.execution_unknown_total += 1

    def record_duplicate(self) -> None:
        self.execution_duplicate_total += 1

    def record_conflict(self) -> None:
        self.execution_conflict_total += 1

    def record_cancel_request(self) -> None:
        self.cancel_requests_total += 1

    def record_cancel_confirmed(self) -> None:
        self.cancel_confirmed_total += 1

    def record_cancel_timeout(self) -> None:
        self.cancel_timeout_total += 1

    def to_dict(self) -> Dict:
        return {
            "execution_requests_total": self.execution_requests_total,
            "execution_ack_total": self.execution_ack_total,
            "execution_reject_total": self.execution_reject_total,
            "execution_timeout_total": self.execution_timeout_total,
            "execution_unknown_total": self.execution_unknown_total,
            "execution_duplicate_total": self.execution_duplicate_total,
            "execution_conflict_total": self.execution_conflict_total,
            "cancel_requests_total": self.cancel_requests_total,
            "cancel_confirmed_total": self.cancel_confirmed_total,
            "cancel_timeout_total": self.cancel_timeout_total,
        }
