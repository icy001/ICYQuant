"""Control decision — the unified decision object produced by the integration layer.

Important: ControlDecision ≠ Approval, ControlDecision ≠ Order.
Decision is the integration layer's judgment: "should we proceed?"
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .control_response import ControlResponse
from .control_constraint import ControlConstraint
from .control_evidence import ControlEvidence
from .control_reason import ReasonCode
from .control_reference import ControlReference


class DecisionStatus(Enum):
    """Outcome of a control decision."""

    ALLOW = auto()
    DENY = auto()
    PENDING = auto()

    @property
    def label(self) -> str:
        _labels = {
            DecisionStatus.ALLOW: "ALLOW",
            DecisionStatus.DENY: "DENY",
            DecisionStatus.PENDING: "PENDING",
        }
        return _labels.get(self, "UNKNOWN")

    @property
    def can_proceed(self) -> bool:
        return self == DecisionStatus.ALLOW


@dataclass
class ControlDecision:
    """Unified decision object produced at the end of the contract chain.

    This is the integration layer's final judgment, distinct from:
      - Approval (formal authorization by an entitled actor)
      - Order (the executable instruction sent to OMS)
    """

    # ── Identity ──

    decision_id: str = field(default_factory=lambda: f"DEC-{uuid.uuid4().hex[:12].upper()}")
    flow_id: str = ""

    # ── Outcome ──

    status: DecisionStatus = DecisionStatus.PENDING
    reason_code: ReasonCode = ReasonCode.RISK_CHECK_PASSED
    reason: str = ""

    # ── Gathered state ──

    responses: List[ControlResponse] = field(default_factory=list)
    constraints: List[ControlConstraint] = field(default_factory=list)
    evidence: List[ControlEvidence] = field(default_factory=list)

    # ── Provenance ──

    policy_version: str = ""
    references: List[ControlReference] = field(default_factory=list)

    # ── Timing ──

    decided_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    # ── Metadata ──

    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory ──

    @classmethod
    def from_responses(
        cls,
        flow_id: str,
        responses: List[ControlResponse],
        constraints: Optional[List[ControlConstraint]] = None,
        evidence: Optional[List[ControlEvidence]] = None,
        references: Optional[List[ControlReference]] = None,
        policy_version: str = "",
        **kwargs: Any,
    ) -> "ControlDecision":
        """Build a decision by aggregating all domain responses."""
        # Determine overall status
        if all(r.passed for r in responses):
            status = DecisionStatus.ALLOW
            reason_code = ReasonCode.APPROVAL_GRANTED
            reason = "All domain gates passed"
        else:
            status = DecisionStatus.DENY
            # Pick the first non-pass reason code
            first_block = next((r for r in responses if not r.passed), responses[0])
            reason_code = first_block.reason_code
            reason = first_block.reason or "Blocked by control gate"

        return cls(
            flow_id=flow_id,
            status=status,
            reason_code=reason_code,
            reason=reason,
            responses=responses,
            constraints=constraints or [],
            evidence=evidence or [],
            references=references or [],
            policy_version=policy_version,
            **kwargs,
        )

    # ── Properties ──

    @property
    def allowed(self) -> bool:
        return self.status.can_proceed

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def response_domains(self) -> List[str]:
        return [r.domain for r in self.responses]

    @property
    def block_reason(self) -> Optional[str]:
        if self.allowed:
            return None
        for r in self.responses:
            if not r.passed:
                return f"{r.domain}: {r.reason_code.name} — {r.reason}"
        return None

    def get_response(self, domain: str) -> Optional[ControlResponse]:
        for r in self.responses:
            if r.domain == domain:
                return r
        return None

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "flow_id": self.flow_id,
            "status": self.status.name,
            "reason_code": self.reason_code.name,
            "reason": self.reason,
            "responses": [r.to_dict() for r in self.responses],
            "constraints": [c.to_dict() for c in self.constraints],
            "evidence": [e.to_dict() for e in self.evidence],
            "policy_version": self.policy_version,
            "references": [r.to_dict() for r in self.references],
            "decided_at": self.decided_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ControlDecision(decision_id={self.decision_id!r}, "
            f"status={self.status.label}, responses={len(self.responses)})"
        )
