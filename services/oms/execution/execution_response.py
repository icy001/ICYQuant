"""ExecutionResponse — ACK from the execution layer."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .execution_status import ExecutionStatus


@dataclass
class ExecutionAck:
    """Acknowledgment from the execution layer.

    An ACK means the execution layer has accepted the order.
    It does NOT mean the order has been filled.
    """

    ack_id: str = ""
    request_id: str = ""
    order_id: str = ""
    status: ExecutionStatus = ExecutionStatus.ACCEPTED
    venue_order_id: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    message: str = ""

    # Lineage
    correlation_id: str = ""
    causation_id: str = ""

    @classmethod
    def accepted(cls, request_id: str, order_id: str,
                 venue_order_id: str = "",
                 correlation_id: str = "") -> "ExecutionAck":
        return cls(
            request_id=request_id,
            order_id=order_id,
            status=ExecutionStatus.ACCEPTED,
            venue_order_id=venue_order_id,
            correlation_id=correlation_id,
        )

    @classmethod
    def rejected(cls, request_id: str, order_id: str,
                 reason: str = "",
                 correlation_id: str = "") -> "ExecutionAck":
        return cls(
            request_id=request_id,
            order_id=order_id,
            status=ExecutionStatus.REJECTED,
            message=reason,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ack_id": self.ack_id,
            "request_id": self.request_id,
            "order_id": self.order_id,
            "status": self.status.name,
            "venue_order_id": self.venue_order_id,
            "timestamp": self.timestamp,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }


@dataclass
class CancelAck:
    """Acknowledgment of a cancel request."""

    cancel_request_id: str = ""
    order_id: str = ""
    status: ExecutionStatus = ExecutionStatus.CANCELLED
    cancelled_quantity: float = 0.0
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    message: str = ""
    correlation_id: str = ""

    @classmethod
    def confirmed(cls, cancel_request_id: str, order_id: str,
                  cancelled_quantity: float = 0,
                  correlation_id: str = "") -> "CancelAck":
        return cls(
            cancel_request_id=cancel_request_id,
            order_id=order_id,
            status=ExecutionStatus.CANCELLED,
            cancelled_quantity=cancelled_quantity,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cancel_request_id": self.cancel_request_id,
            "order_id": self.order_id,
            "status": self.status.name,
            "cancelled_quantity": self.cancelled_quantity,
            "timestamp": self.timestamp,
            "message": self.message,
            "correlation_id": self.correlation_id,
        }
