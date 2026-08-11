"""Mismatch — represents a single reconciliation mismatch."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict

from .mismatch_severity import MismatchSeverity


class MismatchType(Enum):
    """Type of reconciliation mismatch."""

    STATUS_MISMATCH = auto()
    QUANTITY_MISMATCH = auto()
    PRICE_MISMATCH = auto()
    MISSING_EXECUTION = auto()
    DUPLICATE_EXECUTION = auto()
    MISSING_ORDER = auto()
    DUPLICATE_ORDER = auto()

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass
class Mismatch:
    """A single mismatch between OMS and Execution state."""

    mismatch_id: str = field(
        default_factory=lambda: f"MM-{__import__('uuid').uuid4().hex[:8].upper()}"
    )
    order_id: str = ""
    mismatch_type: MismatchType = MismatchType.STATUS_MISMATCH
    severity: MismatchSeverity = MismatchSeverity.WARNING

    oms_value: str = ""
    execution_value: str = ""
    field_name: str = ""

    description: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    @classmethod
    def status_mismatch(cls, order_id: str,
                        oms_status: str,
                        execution_status: str) -> "Mismatch":
        severity = (MismatchSeverity.CRITICAL
                    if "CANCELLED" in oms_status or "REJECTED" in oms_status
                    else MismatchSeverity.ERROR)
        return cls(
            order_id=order_id,
            mismatch_type=MismatchType.STATUS_MISMATCH,
            severity=severity,
            oms_value=oms_status,
            execution_value=execution_status,
            field_name="status",
            description=f"OMS status={oms_status} vs Execution={execution_status}",
        )

    @classmethod
    def quantity_mismatch(cls, order_id: str,
                          oms_qty: float,
                          execution_qty: float) -> "Mismatch":
        return cls(
            order_id=order_id,
            mismatch_type=MismatchType.QUANTITY_MISMATCH,
            severity=MismatchSeverity.ERROR,
            oms_value=str(oms_qty),
            execution_value=str(execution_qty),
            field_name="filled_quantity",
            description=f"OMS filled={oms_qty} vs Execution={execution_qty}",
        )

    @classmethod
    def missing_execution(cls, order_id: str,
                          execution_id: str) -> "Mismatch":
        return cls(
            order_id=order_id,
            mismatch_type=MismatchType.MISSING_EXECUTION,
            severity=MismatchSeverity.ERROR,
            execution_value=execution_id,
            field_name="execution_id",
            description=f"Execution {execution_id} missing from OMS",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mismatch_id": self.mismatch_id,
            "order_id": self.order_id,
            "mismatch_type": self.mismatch_type.name,
            "severity": self.severity.name,
            "oms_value": self.oms_value,
            "execution_value": self.execution_value,
            "field_name": self.field_name,
            "description": self.description,
            "timestamp": self.timestamp,
        }
