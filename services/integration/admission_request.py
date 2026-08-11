"""AdmissionRequest — unified request entering the admission boundary.

Wraps an OrderIntent with all the upstream control decisions and context
needed for the admission pipeline to validate, authorize, and admit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_intent import OrderIntent


@dataclass
class AdmissionRequest:
    """Unified admission request.

    Carries the OrderIntent plus the results of all upstream control checks,
    providing the admission boundary with everything it needs to make a
    final governed decision.
    """

    request_id: str = field(
        default_factory=lambda: f"ADMREQ-{uuid.uuid4().hex[:12].upper()}"
    )
    intent: Optional[OrderIntent] = None

    # Upstream gate results (contract-level)
    risk_passed: bool = False
    governance_passed: bool = False
    authority_passed: bool = False
    approval_passed: bool = False

    # Upstream response IDs
    risk_response_id: str = ""
    governance_response_id: str = ""
    authority_response_id: str = ""
    approval_response_id: str = ""

    # Policy versions from upstream
    policy_version: str = ""
    risk_version: str = ""
    governance_version: str = ""
    authority_version: str = ""
    approval_version: str = ""

    # Approval details
    approval_id: str = ""
    approval_status: str = ""
    approval_amount: Optional[float] = None
    approval_expiry: Optional[float] = None
    approval_scope: str = ""
    approval_policy_version: str = ""

    # Authority details
    authority_id: str = ""
    authority_scope: str = ""
    authority_limit: Optional[float] = None
    authority_expiry: Optional[float] = None
    authority_revoked: bool = False

    # Governance state
    governance_state: str = "NORMAL"

    # Idempotency key for duplicate detection
    idempotency_key: str = ""

    # Emergency flag
    is_emergency: bool = False

    # Metadata
    created_at: float = field(default_factory=lambda: __import__("time").time())

    @classmethod
    def from_intent(cls, intent: OrderIntent) -> "AdmissionRequest":
        return cls(intent=intent, idempotency_key=f"{intent.flow_id}:{intent.intent_id}")

    def with_risk_result(self, passed: bool, response_id: str = "") -> "AdmissionRequest":
        self.risk_passed = passed
        self.risk_response_id = response_id
        return self

    def with_governance_result(self, passed: bool, response_id: str = "", state: str = "") -> "AdmissionRequest":
        self.governance_passed = passed
        self.governance_response_id = response_id
        if state:
            self.governance_state = state
        return self

    def with_authority_result(
        self,
        passed: bool,
        response_id: str = "",
        authority_id: str = "",
        limit: Optional[float] = None,
    ) -> "AdmissionRequest":
        self.authority_passed = passed
        self.authority_response_id = response_id
        self.authority_id = authority_id
        self.authority_limit = limit
        return self

    def with_approval_result(
        self,
        passed: bool,
        response_id: str = "",
        approval_id: str = "",
        status: str = "",
        amount: Optional[float] = None,
        expiry: Optional[float] = None,
        scope: str = "",
    ) -> "AdmissionRequest":
        self.approval_passed = passed
        self.approval_response_id = response_id
        self.approval_id = approval_id
        self.approval_status = status
        self.approval_amount = amount
        self.approval_expiry = expiry
        self.approval_scope = scope
        return self

    def with_emergency(self) -> "AdmissionRequest":
        self.is_emergency = True
        return self

    @property
    def all_gates_passed(self) -> bool:
        return all([
            self.risk_passed,
            self.governance_passed,
            self.authority_passed,
            self.approval_passed,
        ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "intent": self.intent.to_dict() if self.intent else None,
            "risk_passed": self.risk_passed,
            "governance_passed": self.governance_passed,
            "authority_passed": self.authority_passed,
            "approval_passed": self.approval_passed,
            "risk_response_id": self.risk_response_id,
            "governance_response_id": self.governance_response_id,
            "authority_response_id": self.authority_response_id,
            "approval_response_id": self.approval_response_id,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "governance_version": self.governance_version,
            "authority_version": self.authority_version,
            "approval_version": self.approval_version,
            "approval_id": self.approval_id,
            "approval_status": self.approval_status,
            "approval_amount": self.approval_amount,
            "approval_expiry": self.approval_expiry,
            "approval_scope": self.approval_scope,
            "approval_policy_version": self.approval_policy_version,
            "authority_id": self.authority_id,
            "authority_scope": self.authority_scope,
            "authority_limit": self.authority_limit,
            "authority_expiry": self.authority_expiry,
            "authority_revoked": self.authority_revoked,
            "governance_state": self.governance_state,
            "idempotency_key": self.idempotency_key,
            "is_emergency": self.is_emergency,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionRequest(id={self.request_id}, flow={self.intent.flow_id if self.intent else 'N/A'}, "
            f"gates=[risk={self.risk_passed}, gov={self.governance_passed}, "
            f"auth={self.authority_passed}, apr={self.approval_passed}])"
        )
