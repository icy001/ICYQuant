"""
Order Admission — the final gate that decides whether an order is eligible to
enter the OMS (Commit 26 Part 1.2).

Order Admission chains Risk Engine → Institutional Control Gateway →
Position Effect → Final Decision, so an order can no longer reach the OMS
just by passing the Risk Engine.
"""

from __future__ import annotations

from .audit import (
    AdmissionAuditEventType,
    AdmissionAuditRecord,
)
from .decision import (
    AdmissionDecision,
    AdmissionReason,
    OrderAdmissionDecision,
)
from .errors import (
    AdmissionError,
    InvalidAdmissionRequestError,
)
from .evidence import AdmissionEvidence
from .policy import AdmissionPolicy
from .position_validator import (
    PositionEffect,
    PositionEffectValidator,
)
from .repository import AdmissionRepository
from .request import OrderAdmissionRequest
from .risk import RiskDecision, RiskResult
from .service import OrderAdmissionService
from .validator import OrderAdmissionValidator

__all__ = [
    "AdmissionAuditEventType",
    "AdmissionAuditRecord",
    "AdmissionDecision",
    "AdmissionError",
    "AdmissionEvidence",
    "AdmissionPolicy",
    "AdmissionReason",
    "AdmissionRepository",
    "InvalidAdmissionRequestError",
    "OrderAdmissionDecision",
    "OrderAdmissionRequest",
    "OrderAdmissionService",
    "OrderAdmissionValidator",
    "PositionEffect",
    "PositionEffectValidator",
    "RiskDecision",
    "RiskResult",
]
