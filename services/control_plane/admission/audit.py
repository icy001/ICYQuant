"""
Admission audit — the immutable event trail of Order Admission (spec section
14).

Every order that crosses the admission boundary produces a sequence:

    ORDER_ADMISSION_REQUESTED
        ↓
    RISK_APPROVED
        ↓
    CONTROL_EVALUATED
        ↓
    ORDER_ADMISSION_ACCEPTED            (or ORDER_ADMISSION_REJECTED)

so an Order ID, Request ID, Incident ID, Control ID, Strategy ID and Account
ID can all be correlated afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class AdmissionAuditEventType(str, Enum):

    ORDER_ADMISSION_REQUESTED = "ORDER_ADMISSION_REQUESTED"

    RISK_APPROVED = "RISK_APPROVED"

    RISK_REJECTED = "RISK_REJECTED"

    CONTROL_EVALUATED = "CONTROL_EVALUATED"

    ORDER_ADMISSION_ACCEPTED = "ORDER_ADMISSION_ACCEPTED"

    ORDER_ADMISSION_ACCEPTED_REDUCE_ONLY = (
        "ORDER_ADMISSION_ACCEPTED_REDUCE_ONLY"
    )

    ORDER_ADMISSION_REJECTED = "ORDER_ADMISSION_REJECTED"


@dataclass(frozen=True)
class AdmissionAuditRecord:

    event_type: AdmissionAuditEventType

    request_id: UUID

    payload: dict[str, Any] = field(default_factory=dict)

    record_id: UUID = field(default_factory=uuid4)

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    actor: str = "order-admission"
