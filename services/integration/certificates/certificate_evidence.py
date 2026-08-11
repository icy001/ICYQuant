"""CertificateEvidence — immutable snapshot of pre-trade control state.

Evidence captures the factual state at the moment of certificate issuance.
It is NOT real-time data; it is a frozen snapshot for audit and verification.

Evidence kinds:
- RISK: portfolio exposure, margin, limits at issuance time
- GOVERNANCE: governance state (NORMAL/WATCH/RESTRICTED/FROZEN/EMERGENCY)
- AUTHORITY: authority_id, limit, scope at issuance time
- APPROVAL: approval_id, status, amount, expiry at issuance time
- CONSTRAINTS: effective constraint values at issuance time
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List


class EvidenceKind(Enum):
    """Kind of evidence captured in the certificate snapshot."""
    RISK = auto()
    GOVERNANCE = auto()
    AUTHORITY = auto()
    APPROVAL = auto()
    CONSTRAINTS = auto()

    @property
    def label(self) -> str:
        _labels = {
            EvidenceKind.RISK: "Risk",
            EvidenceKind.GOVERNANCE: "Governance",
            EvidenceKind.AUTHORITY: "Authority",
            EvidenceKind.APPROVAL: "Approval",
            EvidenceKind.CONSTRAINTS: "Constraints",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class CertificateEvidence:
    """A single piece of frozen evidence within a certificate.

    Each evidence record represents the state of ONE control domain
    at the exact instant the certificate was issued.
    """

    evidence_id: str = field(
        default_factory=lambda: (
            f"EVID-{__import__('uuid').uuid4().hex[:12].upper()}"
        )
    )
    kind: EvidenceKind = EvidenceKind.RISK

    # ── Key-value snapshot ────────────────────────────────────
    data: Dict[str, Any] = field(default_factory=dict)

    # ── Timestamp of capture ──────────────────────────────────
    captured_at: float = field(default_factory=lambda: time.time())

    # ── Source identification ─────────────────────────────────
    source_gate: str = ""
    source_version: str = ""

    @classmethod
    def risk_evidence(
        cls,
        portfolio_exposure: float = 0.0,
        limit: float = 0.0,
        available_margin: float = 0.0,
        **extras: Any,
    ) -> "CertificateEvidence":
        """Capture risk state snapshot."""
        data = {
            "portfolio_exposure": portfolio_exposure,
            "limit": limit,
            "available_margin": available_margin,
            **extras,
        }
        return cls(kind=EvidenceKind.RISK, data=data)

    @classmethod
    def governance_evidence(
        cls, governance_state: str = "NORMAL", **extras: Any
    ) -> "CertificateEvidence":
        """Capture governance state snapshot."""
        data = {"governance_state": governance_state, **extras}
        return cls(kind=EvidenceKind.GOVERNANCE, data=data)

    @classmethod
    def authority_evidence(
        cls,
        authority_id: str = "",
        authority_limit: float = 0.0,
        requested: float = 0.0,
        **extras: Any,
    ) -> "CertificateEvidence":
        """Capture authority state snapshot."""
        data = {
            "authority_id": authority_id,
            "authority_limit": authority_limit,
            "requested": requested,
            **extras,
        }
        return cls(kind=EvidenceKind.AUTHORITY, data=data)

    @classmethod
    def approval_evidence(
        cls,
        approval_id: str = "",
        status: str = "",
        approved_amount: float = 0.0,
        **extras: Any,
    ) -> "CertificateEvidence":
        """Capture approval state snapshot."""
        data = {
            "approval_id": approval_id,
            "status": status,
            "approved_amount": approved_amount,
            **extras,
        }
        return cls(kind=EvidenceKind.APPROVAL, data=data)

    @classmethod
    def constraints_evidence(
        cls, constraints: Dict[str, Any], **extras: Any
    ) -> "CertificateEvidence":
        """Capture effective constraints snapshot."""
        data = {"constraints": constraints, **extras}
        return cls(kind=EvidenceKind.CONSTRAINTS, data=data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind.name,
            "data": self.data,
            "captured_at": self.captured_at,
            "source_gate": self.source_gate,
            "source_version": self.source_version,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateEvidence(kind={self.kind.name}, "
            f"keys={list(self.data.keys())})"
        )


def combine_evidence_hash(evidences: List[CertificateEvidence]) -> str:
    """Compute a deterministic hash over a list of evidence records.

    Used to produce the certificate's evidence_hash for integrity verification.
    """
    import hashlib
    import json

    sorted_data = sorted(
        [
            {"kind": e.kind.name, "data": e.data}
            for e in evidences
        ],
        key=lambda x: x["kind"],
    )
    raw = json.dumps(sorted_data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
