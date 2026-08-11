"""ReconciliationResult — result of reconciling an order."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .reconciliation_status import ReconciliationStatus
from .mismatch import Mismatch
from .mismatch_severity import MismatchSeverity


@dataclass
class ReconciliationResult:
    """Result of reconciling OMS state with Execution state."""

    reconciliation_id: str = field(
        default_factory=lambda: f"REC-{__import__('uuid').uuid4().hex[:8].upper()}"
    )
    order_id: str = ""

    status: ReconciliationStatus = ReconciliationStatus.UNKNOWN

    oms_status: str = ""
    execution_status: str = ""

    oms_filled_quantity: float = 0.0
    execution_filled_quantity: float = 0.0

    oms_average_price: float = 0.0
    execution_average_price: float = 0.0

    mismatches: List[Mismatch] = field(default_factory=list)

    timestamp: float = field(default_factory=lambda: __import__("time").time())
    latency: float = 0.0

    @property
    def is_consistent(self) -> bool:
        return self.status == ReconciliationStatus.CONSISTENT

    @property
    def has_mismatches(self) -> bool:
        return len(self.mismatches) > 0

    @property
    def max_severity(self) -> MismatchSeverity:
        if not self.mismatches:
            return MismatchSeverity.INFO
        severity_order = {
            MismatchSeverity.INFO: 0,
            MismatchSeverity.WARNING: 1,
            MismatchSeverity.ERROR: 2,
            MismatchSeverity.CRITICAL: 3,
        }
        return max(self.mismatches, key=lambda m: severity_order[m.severity]).severity

    def add_mismatch(self, mismatch: Mismatch) -> None:
        self.mismatches.append(mismatch)
        if mismatch.severity == MismatchSeverity.CRITICAL:
            self.status = ReconciliationStatus.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reconciliation_id": self.reconciliation_id,
            "order_id": self.order_id,
            "status": self.status.name,
            "oms_status": self.oms_status,
            "execution_status": self.execution_status,
            "oms_filled_quantity": self.oms_filled_quantity,
            "execution_filled_quantity": self.execution_filled_quantity,
            "oms_average_price": self.oms_average_price,
            "execution_average_price": self.execution_average_price,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "max_severity": self.max_severity.name,
            "timestamp": self.timestamp,
            "latency": self.latency,
        }
