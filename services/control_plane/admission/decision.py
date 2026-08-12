"""
OrderAdmissionDecision — the final verdict of Order Admission (spec section 4).

    ACCEPTED                → the order may proceed to the OMS
    ACCEPTED_REDUCE_ONLY    → accepted, but only as a position-reducing order
    REJECTED                → the order is refused

Every decision carries the request_id so it can be traced end to end, plus the
underlying Risk and Control results for full evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class AdmissionDecision(str, Enum):

    ACCEPTED = "ACCEPTED"

    ACCEPTED_REDUCE_ONLY = (
        "ACCEPTED_REDUCE_ONLY"
    )

    REJECTED = "REJECTED"

    @property
    def accepted(self) -> bool:
        return self is not AdmissionDecision.REJECTED


class AdmissionReason(str, Enum):

    CONTROL_ALLOWED = "CONTROL_ALLOWED"

    CONTROL_REDUCE_ONLY = (
        "CONTROL_REDUCE_ONLY"
    )

    CONTROL_BLOCKED = (
        "CONTROL_BLOCKED"
    )

    RISK_REJECTED = (
        "RISK_REJECTED"
    )

    INVALID_REQUEST = (
        "INVALID_REQUEST"
    )


@dataclass(frozen=True)
class OrderAdmissionDecision:

    decision: AdmissionDecision

    reason: AdmissionReason

    request_id: UUID

    message: str = ""

    control_result: object | None = None

    risk_result: object | None = None
