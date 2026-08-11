"""OrderCertificate — proof that an order has passed institutional admission.

The certificate is the cryptographic proof that the order intent has been
fully validated, authorized, normalized, and admitted. OMS must reject any
order without a valid certificate.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class CertificateStatus(Enum):
    """Certificate validity status."""
    VALID = auto()
    EXPIRED = auto()
    REVOKED = auto()
    TAMPERED = auto()

    @property
    def label(self) -> str:
        _labels = {
            CertificateStatus.VALID: "VALID",
            CertificateStatus.EXPIRED: "EXPIRED",
            CertificateStatus.REVOKED: "REVOKED",
            CertificateStatus.TAMPERED: "TAMPERED",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class OrderCertificate:
    """Proof of institutional admission.

    Contains all hashes needed to verify that the order entering OMS
    matches exactly what was admitted. Any tampering with the order
    after admission will cause hash mismatch and OMS rejection.
    """

    certificate_id: str = field(
        default_factory=lambda: f"CERT-{uuid.uuid4().hex[:12].upper()}"
    )

    # Identity chain
    order_intent_id: str = ""
    flow_id: str = ""
    decision_id: str = ""
    order_id: str = ""

    # Version chain (for policy-lock verification)
    policy_version: str = ""
    risk_version: str = ""
    governance_version: str = ""
    authority_version: str = ""
    approval_version: str = ""

    # Authority & Approval references
    authority_id: str = ""
    approval_id: str = ""

    # Integrity hashes
    intent_hash: str = ""
    constraints_hash: str = ""
    policy_hash: str = ""
    fingerprint: str = ""

    # Status
    status: CertificateStatus = CertificateStatus.VALID

    # Timestamps
    admitted_at: float = field(default_factory=lambda: time.time())
    expires_at: Optional[float] = None

    @classmethod
    def create(
        cls,
        intent: Dict[str, Any],
        constraints: Dict[str, Any],
        policy: Dict[str, Any],
        fingerprint: str,
        flow_id: str = "",
        decision_id: str = "",
        order_id: str = "",
        authority_id: str = "",
        approval_id: str = "",
        versions: Optional[Dict[str, str]] = None,
        ttl_seconds: float = 300.0,
    ) -> "OrderCertificate":
        """Create a certificate from admission outputs."""
        intent_hash = cls._hash_dict(intent)
        constraints_hash = cls._hash_dict(constraints)
        policy_hash = cls._hash_dict(policy)

        cert = cls(
            order_intent_id=intent.get("intent_id", ""),
            flow_id=flow_id,
            decision_id=decision_id,
            order_id=order_id,
            authority_id=authority_id,
            approval_id=approval_id,
            intent_hash=intent_hash,
            constraints_hash=constraints_hash,
            policy_hash=policy_hash,
            fingerprint=fingerprint,
            admitted_at=time.time(),
            expires_at=time.time() + ttl_seconds,
        )

        if versions:
            cert.policy_version = versions.get("policy", "")
            cert.risk_version = versions.get("risk", "")
            cert.governance_version = versions.get("governance", "")
            cert.authority_version = versions.get("authority", "")
            cert.approval_version = versions.get("approval", "")

        return cert

    @staticmethod
    def _hash_dict(d: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of a dictionary."""
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_intent(self, intent: Dict[str, Any]) -> bool:
        """Verify that an intent matches the certificate's intent_hash."""
        return self._hash_dict(intent) == self.intent_hash

    def verify_constraints(self, constraints: Dict[str, Any]) -> bool:
        """Verify that constraints match the certificate's constraints_hash."""
        return self._hash_dict(constraints) == self.constraints_hash

    def is_expired(self) -> bool:
        """Check if certificate has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def validate(self) -> CertificateStatus:
        """Check certificate validity."""
        if self.status != CertificateStatus.VALID:
            return self.status
        if self.is_expired():
            self.status = CertificateStatus.EXPIRED
            return CertificateStatus.EXPIRED
        if not self.intent_hash or not self.fingerprint:
            self.status = CertificateStatus.TAMPERED
            return CertificateStatus.TAMPERED
        return CertificateStatus.VALID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "order_intent_id": self.order_intent_id,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "order_id": self.order_id,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "governance_version": self.governance_version,
            "authority_version": self.authority_version,
            "approval_version": self.approval_version,
            "authority_id": self.authority_id,
            "approval_id": self.approval_id,
            "intent_hash": self.intent_hash,
            "constraints_hash": self.constraints_hash,
            "policy_hash": self.policy_hash,
            "fingerprint": self.fingerprint,
            "status": self.status.name,
            "admitted_at": self.admitted_at,
            "expires_at": self.expires_at,
        }

    def __repr__(self) -> str:
        return (
            f"OrderCertificate(id={self.certificate_id}, flow={self.flow_id}, "
            f"status={self.status.label}, intent_hash={self.intent_hash[:12]}...)"
        )
