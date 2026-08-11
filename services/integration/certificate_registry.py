"""CertificateRegistry — authoritative record of all certificate lifecycle events.

Tracks:
- Issuance (when, by what flow)
- Status transitions (ISSUED → VALID → USED, or → REVOKED/EXPIRED)
- Revocation (when, why)
- Expiry

The Registry is the source of truth for "is this certificate still valid?"
OMS and Execution query the Registry before accepting any order.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .certificates.certificate_status import CertificateStatus
from .certificates.pre_trade_certificate import PreTradeControlCertificate


@dataclass
class CertificateRecord:
    """A single record in the certificate registry."""
    record_id: str = field(
        default_factory=lambda: f"CREC-{uuid.uuid4().hex[:12].upper()}"
    )
    certificate_id: str = ""
    flow_id: str = ""
    order_intent_id: str = ""
    decision_id: str = ""
    account_id: str = ""

    # ── Status tracking ──────────────────────────────────────
    status: str = CertificateStatus.ISSUED.name

    # ── Timestamps ───────────────────────────────────────────
    issued_at: float = 0.0
    expires_at: Optional[float] = None
    used_at: Optional[float] = None
    revoked_at: Optional[float] = None
    revocation_reason: str = ""

    # ── Scope summary ────────────────────────────────────────
    symbol: str = ""
    side: str = ""
    max_quantity: Optional[float] = None
    max_notional: Optional[float] = None

    # ── Policy versions ──────────────────────────────────────
    policy_versions: Dict[str, str] = field(default_factory=dict)

    # ── Fingerprint ──────────────────────────────────────────
    certificate_fingerprint: str = ""

    @classmethod
    def from_certificate(
        cls, cert: PreTradeControlCertificate
    ) -> "CertificateRecord":
        """Create a registry record from a certificate."""
        return cls(
            certificate_id=cert.certificate_id,
            flow_id=cert.flow_id,
            order_intent_id=cert.order_intent_id,
            decision_id=cert.decision_id,
            account_id=cert.account_id,
            status=cert.status.name,
            issued_at=cert.issued_at,
            expires_at=cert.expires_at,
            used_at=cert.used_at,
            revoked_at=cert.revoked_at,
            revocation_reason=cert.revocation_reason,
            symbol=cert.scope.symbol,
            side=cert.scope.side,
            max_quantity=cert.scope.max_quantity,
            max_notional=cert.scope.max_notional,
            policy_versions=dict(cert.policy_versions),
            certificate_fingerprint=(
                cert.fingerprint.fingerprint_hash if cert.fingerprint else ""
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "certificate_id": self.certificate_id,
            "flow_id": self.flow_id,
            "order_intent_id": self.order_intent_id,
            "decision_id": self.decision_id,
            "account_id": self.account_id,
            "status": self.status,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "used_at": self.used_at,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "symbol": self.symbol,
            "side": self.side,
            "max_quantity": self.max_quantity,
            "max_notional": self.max_notional,
            "policy_versions": self.policy_versions,
            "certificate_fingerprint": self.certificate_fingerprint,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateRecord(id={self.certificate_id[:12]}..., "
            f"status={self.status}, "
            f"symbol={self.symbol} {self.side})"
        )


@dataclass
class CertificateRegistry:
    """Authoritative registry of all certificates and their lifecycle events.

    OMS and Execution query this registry before accepting any order.
    """

    # ── Storage ───────────────────────────────────────────────
    _records: Dict[str, CertificateRecord] = field(default_factory=dict)
    _revoked_ids: set = field(default_factory=set)
    _audit_log: List[Dict[str, Any]] = field(default_factory=list)

    # ── Registration ──────────────────────────────────────────

    def register(self, cert: PreTradeControlCertificate) -> CertificateRecord:
        """Register a certificate in the registry."""
        record = CertificateRecord.from_certificate(cert)
        self._records[cert.certificate_id] = record
        self._log_event("REGISTERED", cert.certificate_id)
        return record

    def update_status(
        self, cert_id: str, new_status: CertificateStatus
    ) -> Optional[CertificateRecord]:
        """Update a certificate's status in the registry."""
        record = self._records.get(cert_id)
        if record is None:
            return None
        record.status = new_status.name

        if new_status == CertificateStatus.USED:
            record.used_at = time.time()
        elif new_status == CertificateStatus.REVOKED:
            record.revoked_at = time.time()

        self._log_event(f"STATUS_{new_status.name}", cert_id)
        return record

    def revoke(
        self, cert_id: str, reason: str
    ) -> Optional[CertificateRecord]:
        """Record a certificate revocation."""
        record = self._records.get(cert_id)
        if record is None:
            return None
        record.status = CertificateStatus.REVOKED.name
        record.revoked_at = time.time()
        record.revocation_reason = reason
        self._revoked_ids.add(cert_id)
        self._log_event("REVOKED", cert_id, {"reason": reason})
        return record

    # ── Queries ───────────────────────────────────────────────

    def is_valid(self, cert_id: str) -> bool:
        """Check whether a certificate is still valid (not revoked, not used)."""
        record = self._records.get(cert_id)
        if record is None:
            return False
        if cert_id in self._revoked_ids:
            return False
        if record.status in {
            CertificateStatus.REVOKED.name,
            CertificateStatus.EXPIRED.name,
            CertificateStatus.INVALID.name,
            CertificateStatus.USED.name,
        }:
            return False
        return True

    def is_revoked(self, cert_id: str) -> bool:
        """Check whether a certificate has been revoked."""
        return cert_id in self._revoked_ids

    def get_record(self, cert_id: str) -> Optional[CertificateRecord]:
        """Get a certificate record by ID."""
        return self._records.get(cert_id)

    def get_by_flow(self, flow_id: str) -> List[CertificateRecord]:
        """Get all certificates for a given flow."""
        return [
            r for r in self._records.values() if r.flow_id == flow_id
        ]

    def get_by_intent(self, intent_id: str) -> List[CertificateRecord]:
        """Get all certificates for a given order intent."""
        return [
            r for r in self._records.values()
            if r.order_intent_id == intent_id
        ]

    def get_by_account(self, account_id: str) -> List[CertificateRecord]:
        """Get all certificates for a given account."""
        return [
            r for r in self._records.values()
            if r.account_id == account_id
        ]

    # ── Audit ─────────────────────────────────────────────────

    def _log_event(
        self, event_type: str, cert_id: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        self._audit_log.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "certificate_id": cert_id,
            "extra": extra or {},
        })

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return the full audit log."""
        return list(self._audit_log)

    def get_audit_log_for(self, cert_id: str) -> List[Dict[str, Any]]:
        """Return audit log entries for a specific certificate."""
        return [
            entry for entry in self._audit_log
            if entry["certificate_id"] == cert_id
        ]

    # ── Stats ─────────────────────────────────────────────────

    @property
    def total_issued(self) -> int:
        return len(self._records)

    @property
    def total_revoked(self) -> int:
        return len(self._revoked_ids)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_issued": self.total_issued,
            "total_revoked": self.total_revoked,
            "records": {
                k: v.to_dict() for k, v in self._records.items()
            },
        }
