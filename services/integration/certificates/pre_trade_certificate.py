"""PreTradeControlCertificate — immutable proof of institutional pre-trade control.

This is the core artifact of Part 1.4. It is NOT a simple "approved = true" flag.
It records:

- WHY this order was allowed (all gate decisions)
- WHO allowed it (authority, approval identities)
- UNDER WHAT POLICY (version-locked policy references)
- WHAT CONSTRAINTS apply (scope: max quantity, notional, leverage)
- WHEN it was issued and when it expires
- WHAT EVIDENCE existed at issuance time (frozen snapshot)

The certificate is the final bridge between the Decision world and the
Execution world. OMS must verify it. Audit must be able to reconstruct
the full approval lineage from it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .certificate_status import CertificateStatus, can_transition
from .certificate_scope import CertificateScope, ConsumptionMode
from .certificate_claim import CertificateClaim
from .certificate_evidence import CertificateEvidence, EvidenceKind, combine_evidence_hash
from .certificate_signature import CertificateSignature
from .certificate_fingerprint import CertificateFingerprint


@dataclass
class PreTradeControlCertificate:
    """Immutable proof that an OrderIntent passed all pre-trade control gates.

    This certificate is the ONLY thing that authorizes an order to enter OMS.
    Without it, no order reaches execution.
    """

    # ── Identity ──────────────────────────────────────────────
    certificate_id: str = field(
        default_factory=lambda: f"CERT-{uuid.uuid4().hex[:12].upper()}"
    )

    # ── Upstream lineage ──────────────────────────────────────
    flow_id: str = ""
    decision_id: str = ""
    signal_id: str = ""
    strategy_id: str = ""

    # ── Order binding ─────────────────────────────────────────
    order_intent_id: str = ""
    order_id: str = ""
    account_id: str = ""
    portfolio_id: str = ""

    # ── Intent integrity ──────────────────────────────────────
    intent_hash: str = ""

    # ── Scope ─────────────────────────────────────────────────
    scope: CertificateScope = field(default_factory=CertificateScope)

    # ── Control claims (one per gate) ─────────────────────────
    risk_claim: Optional[CertificateClaim] = None
    governance_claim: Optional[CertificateClaim] = None
    authority_claim: Optional[CertificateClaim] = None
    approval_claim: Optional[CertificateClaim] = None

    # ── Evidence snapshot ─────────────────────────────────────
    evidence: List[CertificateEvidence] = field(default_factory=list)

    # ── Policy version lock ───────────────────────────────────
    policy_versions: Dict[str, str] = field(default_factory=dict)
    #  e.g. {"risk": "RISK-v8", "governance": "GOV-v5",
    #         "authority": "AUTH-v3", "approval": "APPROVAL-v2"}

    # ── Effective constraints ─────────────────────────────────
    effective_constraints: Dict[str, Any] = field(default_factory=dict)

    # ── Certificate integrity ─────────────────────────────────
    signature: Optional[CertificateSignature] = None
    fingerprint: Optional[CertificateFingerprint] = None

    @property
    def evidence_hash(self) -> str:
        """Compute hash of all evidence items."""
        return combine_evidence_hash(self.evidence)

    # ── Status ────────────────────────────────────────────────
    status: CertificateStatus = CertificateStatus.ISSUED

    # ── Timestamps ────────────────────────────────────────────
    issued_at: float = field(default_factory=lambda: time.time())
    expires_at: Optional[float] = None
    used_at: Optional[float] = None
    revoked_at: Optional[float] = None
    revocation_reason: str = ""

    # ── Usage tracking ────────────────────────────────────────
    use_count: int = 0

    @property
    def is_active(self) -> bool:
        """Whether the certificate is currently usable."""
        now = time.time()
        if not self.status.is_active:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if certificate TTL has elapsed."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def is_one_time(self) -> bool:
        """Whether this is a single-use certificate."""
        return self.scope.consumption_mode == ConsumptionMode.ONE_TIME

    # ── Lifecycle methods ─────────────────────────────────────

    def transition_to(self, new_status: CertificateStatus) -> "PreTradeControlCertificate":
        """Transition certificate to a new status."""
        if not can_transition(self.status, new_status):
            raise ValueError(
                f"Invalid certificate transition: "
                f"{self.status.label} → {new_status.label}"
            )
        self.status = new_status
        return self

    def activate(self) -> "PreTradeControlCertificate":
        """Mark certificate as VALID after issuance verification."""
        self.transition_to(CertificateStatus.VALID)
        return self

    def mark_used(self) -> "PreTradeControlCertificate":
        """Mark certificate as USED (one-time or fully consumed)."""
        self.transition_to(CertificateStatus.USED)
        self.used_at = time.time()
        self.use_count += 1
        return self

    def expire(self) -> "PreTradeControlCertificate":
        """Mark certificate as EXPIRED."""
        self.transition_to(CertificateStatus.EXPIRED)
        return self

    def revoke(self, reason: str) -> "PreTradeControlCertificate":
        """Revoke the certificate with a reason."""
        self.transition_to(CertificateStatus.REVOKED)
        self.revoked_at = time.time()
        self.revocation_reason = reason
        return self

    def invalidate(self) -> "PreTradeControlCertificate":
        """Mark certificate as INVALID (integrity failure)."""
        self.transition_to(CertificateStatus.INVALID)
        return self

    # ── Claim helpers ─────────────────────────────────────────

    def all_claims_passed(self) -> bool:
        """Check whether all required control claims passed."""
        required = [
            self.risk_claim,
            self.governance_claim,
            self.authority_claim,
            self.approval_claim,
        ]
        return all(c is not None and c.is_pass() for c in required)

    def get_claims(self) -> List[CertificateClaim]:
        """Return all non-None claims."""
        claims = [
            self.risk_claim,
            self.governance_claim,
            self.authority_claim,
            self.approval_claim,
        ]
        return [c for c in claims if c is not None]

    def claims_as_dict_list(self) -> List[Dict[str, Any]]:
        """Return all claims as dicts for signature computation."""
        return [c.to_dict() for c in self.get_claims()]

    def evidence_as_dict_list(self) -> List[Dict[str, Any]]:
        """Return all evidence as dicts for signature computation."""
        return [e.to_dict() for e in self.evidence]

    # ── Fingerprint computation ───────────────────────────────

    def compute_fingerprint(self) -> CertificateFingerprint:
        """Compute and store the certificate fingerprint.

        Must be called after all fields are populated but before signing.
        """
        fp = CertificateFingerprint.compute(
            certificate_id=self.certificate_id,
            flow_id=self.flow_id,
            order_intent_id=self.order_intent_id,
            decision_id=self.decision_id,
            signal_id=self.signal_id,
            strategy_id=self.strategy_id,
            account_id=self.account_id,
            symbol=self.scope.symbol,
            side=self.scope.side,
            max_quantity=self.scope.max_quantity,
            max_notional=self.scope.max_notional,
            venue=self.scope.venue,
            policy_versions=self.policy_versions,
            evidence_hash=self.evidence_hash,
        )
        self.fingerprint = fp
        return fp

    def compute_signature(self) -> CertificateSignature:
        """Compute and store the integrity signature.

        Must be called after compute_fingerprint().
        """
        sig = CertificateSignature.compute(
            certificate_id=self.certificate_id,
            flow_id=self.flow_id,
            order_intent_id=self.order_intent_id,
            intent_hash=self.intent_hash,
            scope_info=self.scope.to_dict(),
            constraints_info=self.effective_constraints,
            policy_versions=self.policy_versions,
            claims_list=self.claims_as_dict_list(),
            evidence_list=self.evidence_as_dict_list(),
        )
        self.signature = sig
        return sig

    def seal(self) -> "PreTradeControlCertificate":
        """Finalize: compute fingerprint + signature, activate."""
        self.compute_fingerprint()
        self.compute_signature()
        self.activate()
        return self

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "order_intent_id": self.order_intent_id,
            "order_id": self.order_id,
            "account_id": self.account_id,
            "portfolio_id": self.portfolio_id,
            "intent_hash": self.intent_hash,
            "status": self.status.name,
            "scope": self.scope.to_dict(),
            "claims": [c.to_dict() for c in self.get_claims()],
            "evidence": [e.to_dict() for e in self.evidence],
            "policy_versions": self.policy_versions,
            "effective_constraints": self.effective_constraints,
            "signature": self.signature.to_dict() if self.signature else None,
            "fingerprint": self.fingerprint.to_dict() if self.fingerprint else None,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "used_at": self.used_at,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "use_count": self.use_count,
        }

    def __repr__(self) -> str:
        return (
            f"PreTradeControlCertificate(id={self.certificate_id[:12]}..., "
            f"flow={self.flow_id}, intent={self.order_intent_id[:12]}..., "
            f"status={self.status.label}, "
            f"scope={self.scope.symbol} {self.scope.side})"
        )


def create_empty_certificate() -> PreTradeControlCertificate:
    """Create an empty certificate instance (for testing)."""
    return PreTradeControlCertificate()
