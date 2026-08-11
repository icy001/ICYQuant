"""ExecutionReport — fill/cancel/reject report from execution layer."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .execution_status import ExecutionStatus


@dataclass
class ExecutionReport:
    """A report from the execution layer about an execution event.

    ExecutionReports carry an execution_id that must be unique.
    Duplicate execution_ids with the same payload are idempotent replays.
    Duplicate execution_ids with different payloads are conflicts.
    """

    execution_id: str = ""
    order_id: str = ""
    request_id: str = ""

    status: ExecutionStatus = ExecutionStatus.UNKNOWN

    executed_quantity: float = 0.0
    executed_price: float = 0.0
    remaining_quantity: float = 0.0

    execution_timestamp: float = field(
        default_factory=lambda: __import__("time").time()
    )
    venue: str = ""
    liquidity_flag: str = ""

    reject_code: str = ""
    reject_reason: str = ""

    # Lineage
    correlation_id: str = ""
    causation_id: str = ""

    @classmethod
    def partial_fill(cls, execution_id: str, order_id: str,
                     executed_quantity: float, executed_price: float,
                     remaining_quantity: float = 0,
                     venue: str = "",
                     correlation_id: str = "") -> "ExecutionReport":
        return cls(
            execution_id=execution_id,
            order_id=order_id,
            status=ExecutionStatus.PARTIALLY_FILLED,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            remaining_quantity=remaining_quantity,
            venue=venue,
            correlation_id=correlation_id,
        )

    @classmethod
    def full_fill(cls, execution_id: str, order_id: str,
                  executed_quantity: float, executed_price: float,
                  venue: str = "",
                  correlation_id: str = "") -> "ExecutionReport":
        return cls(
            execution_id=execution_id,
            order_id=order_id,
            status=ExecutionStatus.FILLED,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            remaining_quantity=0,
            venue=venue,
            correlation_id=correlation_id,
        )

    @classmethod
    def rejected(cls, order_id: str,
                 reject_code: str = "",
                 reject_reason: str = "",
                 correlation_id: str = "") -> "ExecutionReport":
        return cls(
            order_id=order_id,
            status=ExecutionStatus.REJECTED,
            reject_code=reject_code,
            reject_reason=reject_reason,
            correlation_id=correlation_id,
        )

    @classmethod
    def cancelled(cls, order_id: str,
                  cancelled_quantity: float = 0,
                  correlation_id: str = "") -> "ExecutionReport":
        return cls(
            order_id=order_id,
            status=ExecutionStatus.CANCELLED,
            executed_quantity=0,
            remaining_quantity=0,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "order_id": self.order_id,
            "request_id": self.request_id,
            "status": self.status.name,
            "executed_quantity": self.executed_quantity,
            "executed_price": self.executed_price,
            "remaining_quantity": self.remaining_quantity,
            "execution_timestamp": self.execution_timestamp,
            "venue": self.venue,
            "liquidity_flag": self.liquidity_flag,
            "reject_code": self.reject_code,
            "reject_reason": self.reject_reason,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }

    @property
    def is_fill(self) -> bool:
        return self.status.is_fill

    @property
    def is_reject(self) -> bool:
        return self.status.is_rejected
