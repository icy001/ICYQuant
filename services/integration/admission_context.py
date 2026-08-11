"""AdmissionContext — runtime context carried through the admission pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .admission_state import AdmissionState


@dataclass
class AdmissionContext:
    """Runtime context for the admission pipeline.

    Carries identity fields, version tracking, and state through the
    validate → authorize → normalize → dedupe → reserve → admit pipeline.
    """

    admission_id: str = field(
        default_factory=lambda: f"ADM-{uuid.uuid4().hex[:12].upper()}"
    )
    flow_id: str = ""
    decision_id: str = ""
    strategy_id: str = ""
    portfolio_id: str = ""
    account_id: str = ""

    order_id: str = ""
    intent_id: str = ""

    # Version tracking for policy-lock validation
    policy_version: str = ""
    risk_version: str = ""
    governance_version: str = ""
    authority_version: str = ""
    approval_version: str = ""

    # Approval context
    approval_id: str = ""
    approval_policy_version: str = ""

    # Authority context
    authority_id: str = ""
    authority_limit: Optional[float] = None

    # Governance state at admission time
    governance_state: str = "NORMAL"

    # Current admission state
    state: AdmissionState = field(default=AdmissionState.RECEIVED)

    # Error tracking
    last_error_code: str = ""
    last_error_message: str = ""

    # Metadata
    created_at: float = field(default_factory=lambda: __import__("time").time())

    @classmethod
    def from_intent(
        cls,
        intent_id: str,
        flow_id: str,
        decision_id: str,
        strategy_id: str,
        portfolio_id: str,
        account_id: str,
    ) -> "AdmissionContext":
        return cls(
            intent_id=intent_id,
            flow_id=flow_id,
            decision_id=decision_id,
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
        )

    def with_order_id(self, order_id: str) -> "AdmissionContext":
        self.order_id = order_id
        return self

    def with_approval(self, approval_id: str, approval_policy_version: str = "") -> "AdmissionContext":
        self.approval_id = approval_id
        self.approval_policy_version = approval_policy_version
        return self

    def with_authority(self, authority_id: str, authority_limit: Optional[float] = None) -> "AdmissionContext":
        self.authority_id = authority_id
        self.authority_limit = authority_limit
        return self

    def with_governance_state(self, state: str) -> "AdmissionContext":
        self.governance_state = state
        return self

    def with_versions(
        self,
        policy: str = "",
        risk: str = "",
        governance: str = "",
        authority: str = "",
        approval: str = "",
    ) -> "AdmissionContext":
        if policy:
            self.policy_version = policy
        if risk:
            self.risk_version = risk
        if governance:
            self.governance_version = governance
        if authority:
            self.authority_version = authority
        if approval:
            self.approval_version = approval
        return self

    def transition_to(self, state: AdmissionState) -> "AdmissionContext":
        from .admission_state import can_transition
        if not can_transition(self.state, state):
            raise ValueError(
                f"Invalid admission transition: {self.state.label} → {state.label}"
            )
        self.state = state
        return self

    def set_error(self, code: str, message: str = "") -> "AdmissionContext":
        self.last_error_code = code
        self.last_error_message = message
        return self

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    @property
    def is_admitted(self) -> bool:
        return self.state == AdmissionState.ADMITTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admission_id": self.admission_id,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "account_id": self.account_id,
            "order_id": self.order_id,
            "intent_id": self.intent_id,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "governance_version": self.governance_version,
            "authority_version": self.authority_version,
            "approval_version": self.approval_version,
            "approval_id": self.approval_id,
            "approval_policy_version": self.approval_policy_version,
            "authority_id": self.authority_id,
            "authority_limit": self.authority_limit,
            "governance_state": self.governance_state,
            "state": self.state.name,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionContext(id={self.admission_id}, flow={self.flow_id}, "
            f"state={self.state.label}, intent={self.intent_id})"
        )
