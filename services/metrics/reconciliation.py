"""
Reconciliation metrics.

Business metrics for
self-healing system.
"""

from __future__ import annotations

from .counter import Counter
from .gauge import Gauge


class ReconciliationMetrics:
    def __init__(
        self,
    ):
        self.failures = Counter(
            "reconciliation_failures_total"
        )
        self.repairs = Counter(
            "repair_events_total"
        )
        self.pending = Gauge(
            "pending_approvals"
        )
        self.drift = Gauge(
            "state_drift_amount"
        )

    def record_failure(
        self,
    ):
        self.failures.inc()

    def record_repair(
        self,
    ):
        self.repairs.inc()

    def set_pending(
        self,
        value,
    ):
        self.pending.set(
            value
        )

    def set_drift(
        self,
        value,
    ):
        self.drift.set(
            value
        )