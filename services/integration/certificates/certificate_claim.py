"""CertificateClaim — a single verifiable claim within a PreTradeControlCertificate.

Each claim represents one control gate's decision at the time of issuance.
Claims are immutable evidence of "who approved what, when, under what policy."
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ClaimType(Enum):
    """Types of claims that a certificate can carry."""
    RISK = auto()
    GOVERNANCE = auto()
    AUTHORITY = auto()
    APPROVAL = auto()
    ORDER_INTENT = auto()
    CONSTRAINTS = auto()
    POLICY_VERSION = auto()
    FINGERPRINT = auto()


class ClaimDecision(Enum):
    """Outcome of a single control check."""
    PASS = auto()
    FAIL = auto()
    NOT_APPLICABLE = auto()
    OVERRIDDEN = auto()

    @property
    def label(self) -> str:
        _labels = {
            ClaimDecision.PASS: "Pass",
            ClaimDecision.FAIL: "Fail",
            ClaimDecision.NOT_APPLICABLE: "N/A",
            ClaimDecision.OVERRIDDEN: "Overridden",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class CertificateClaim:
    """A single statement of fact recorded at certificate issuance time.

    Immutable by convention — claims should not be modified after creation.
    """

    claim_id: str = field(
        default_factory=lambda: f"CLAIM-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    claim_type: ClaimType = ClaimType.RISK
    decision: ClaimDecision = ClaimDecision.NOT_APPLICABLE

    # ── Identifying information ───────────────────────────────
    gate_id: str = ""
    gate_version: str = ""
    policy_version: str = ""

    # ── Snapshot data at issuance time ────────────────────────
    key: str = ""
    value: Any = None
    detail: Dict[str, Any] = field(default_factory=dict)

    # ── Timestamps ────────────────────────────────────────────
    evaluated_at: float = field(default_factory=lambda: time.time())
    claim_expires_at: Optional[float] = None

    # ── Traceability ──────────────────────────────────────────
    evaluator_id: str = ""
    evaluation_signature: str = ""

    @classmethod
    def risk_claim(
        cls,
        passed: bool,
        gate_id: str = "",
        policy_version: str = "",
        detail: Optional[Dict[str, Any]] = None,
    ) -> "CertificateClaim":
        """Create a claim from a risk gate decision."""
        return cls(
            claim_type=ClaimType.RISK,
            decision=ClaimDecision.PASS if passed else ClaimDecision.FAIL,
            gate_id=gate_id,
            policy_version=policy_version,
            detail=detail or {},
        )

    @classmethod
    def governance_claim(
        cls,
        passed: bool,
        state: str = "",
        gate_id: str = "",
        policy_version: str = "",
    ) -> "CertificateClaim":
        """Create a claim from a governance gate decision."""
        return cls(
            claim_type=ClaimType.GOVERNANCE,
            decision=ClaimDecision.PASS if passed else ClaimDecision.FAIL,
            gate_id=gate_id,
            policy_version=policy_version,
            detail={"governance_state": state},
        )

    @classmethod
    def authority_claim(
        cls,
        passed: bool,
        authority_id: str = "",
        limit: float = 0.0,
        policy_version: str = "",
    ) -> "CertificateClaim":
        """Create a claim from an authority gate decision."""
        return cls(
            claim_type=ClaimType.AUTHORITY,
            decision=ClaimDecision.PASS if passed else ClaimDecision.FAIL,
            gate_id=authority_id,
            policy_version=policy_version,
            detail={"authority_limit": limit},
        )

    @classmethod
    def approval_claim(
        cls,
        passed: bool,
        approval_id: str = "",
        status: str = "",
        amount: float = 0.0,
        policy_version: str = "",
    ) -> "CertificateClaim":
        """Create a claim from an approval gate decision."""
        return cls(
            claim_type=ClaimType.APPROVAL,
            decision=ClaimDecision.PASS if passed else ClaimDecision.FAIL,
            gate_id=approval_id,
            policy_version=policy_version,
            detail={"approval_status": status, "approval_amount": amount},
        )

    def is_pass(self) -> bool:
        """Whether the claim represents a passing check."""
        return self.decision == ClaimDecision.PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type.name,
            "decision": self.decision.name,
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "policy_version": self.policy_version,
            "key": self.key,
            "value": self.value,
            "detail": self.detail,
            "evaluated_at": self.evaluated_at,
            "claim_expires_at": self.claim_expires_at,
            "evaluator_id": self.evaluator_id,
            "evaluation_signature": self.evaluation_signature,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateClaim({self.claim_type.name}, "
            f"decision={self.decision.name}, "
            f"gate={self.gate_id or '-'})"
        )
