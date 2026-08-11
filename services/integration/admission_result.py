"""AdmissionResult — unified result returned from the admission boundary."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class AdmissionResultStatus(Enum):
    """Terminal admission result status."""
    ADMITTED = auto()
    REJECTED = auto()
    BLOCKED = auto()
    DUPLICATE = auto()
    EXPIRED = auto()
    RESERVATION_FAILED = auto()

    @property
    def label(self) -> str:
        _labels = {
            AdmissionResultStatus.ADMITTED: "ADMITTED",
            AdmissionResultStatus.REJECTED: "REJECTED",
            AdmissionResultStatus.BLOCKED: "BLOCKED",
            AdmissionResultStatus.DUPLICATE: "DUPLICATE",
            AdmissionResultStatus.EXPIRED: "EXPIRED",
            AdmissionResultStatus.RESERVATION_FAILED: "RESERVATION_FAILED",
        }
        return _labels.get(self, "UNKNOWN")

    @property
    def is_success(self) -> bool:
        return self == AdmissionResultStatus.ADMITTED


@dataclass
class AdmissionResult:
    """Result returned by the OrderAdmission boundary.

    Contains the final status, certificate (if admitted), and diagnostic
    information for audit and metrics.
    """

    result_id: str = field(
        default_factory=lambda: f"ADMRES-{uuid.uuid4().hex[:12].upper()}"
    )
    status: AdmissionResultStatus = AdmissionResultStatus.REJECTED
    code: str = ""
    message: str = ""

    flow_id: str = ""
    intent_id: str = ""
    order_id: str = ""
    certificate_id: str = ""

    # Diagnostic details
    validation_errors: list = field(default_factory=list)
    rejection_reason: str = ""

    # Timestamps
    admitted_at: Optional[float] = None
    created_at: float = field(default_factory=lambda: time.time())

    @classmethod
    def make_admitted(
        cls,
        flow_id: str,
        intent_id: str,
        order_id: str,
        certificate_id: str,
    ) -> "AdmissionResult":
        return cls(
            status=AdmissionResultStatus.ADMITTED,
            code="ORDER_ADMITTED",
            message="Order admitted successfully",
            flow_id=flow_id,
            intent_id=intent_id,
            order_id=order_id,
            certificate_id=certificate_id,
            admitted_at=time.time(),
        )

    @classmethod
    def make_rejected(cls, code: str, message: str, flow_id: str = "",
                      intent_id: str = "", errors: Optional[list] = None) -> "AdmissionResult":
        return cls(
            status=AdmissionResultStatus.REJECTED,
            code=code,
            message=message,
            flow_id=flow_id,
            intent_id=intent_id,
            validation_errors=errors or [],
            rejection_reason=message,
        )

    @classmethod
    def make_blocked(cls, code: str, message: str, flow_id: str = "",
                     intent_id: str = "") -> "AdmissionResult":
        return cls(
            status=AdmissionResultStatus.BLOCKED,
            code=code,
            message=message,
            flow_id=flow_id,
            intent_id=intent_id,
            rejection_reason=message,
        )

    @classmethod
    def make_duplicate(cls, flow_id: str, intent_id: str,
                       original_order_id: str = "") -> "AdmissionResult":
        return cls(
            status=AdmissionResultStatus.DUPLICATE,
            code="DUPLICATE_ORDER",
            message=f"Duplicate order detected: {original_order_id}",
            flow_id=flow_id,
            intent_id=intent_id,
            order_id=original_order_id,
        )

    @classmethod
    def make_expired(cls, code: str, message: str, flow_id: str = "",
                     intent_id: str = "") -> "AdmissionResult":
        return cls(
            status=AdmissionResultStatus.EXPIRED,
            code=code,
            message=message,
            flow_id=flow_id,
            intent_id=intent_id,
        )

    @classmethod
    def make_reservation_failed(cls, code: str, message: str, flow_id: str = "",
                                intent_id: str = "") -> "AdmissionResult":
        return cls(
            status=AdmissionResultStatus.RESERVATION_FAILED,
            code=code,
            message=message,
            flow_id=flow_id,
            intent_id=intent_id,
            rejection_reason=message,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "status": self.status.name,
            "code": self.code,
            "message": self.message,
            "flow_id": self.flow_id,
            "intent_id": self.intent_id,
            "order_id": self.order_id,
            "certificate_id": self.certificate_id,
            "validation_errors": self.validation_errors,
            "rejection_reason": self.rejection_reason,
            "admitted_at": self.admitted_at,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionResult(status={self.status.label}, code={self.code}, "
            f"flow={self.flow_id}, order={self.order_id})"
        )
