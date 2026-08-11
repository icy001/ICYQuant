"""CertificateLifecycle — manages certificate state transitions and usage tracking.

Handles:
- Activating newly issued certificates
- Marking certificates as USED (with consumption tracking)
- Revoking certificates (with reason recording)
- Expiry handling
- Replay detection
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .certificates.pre_trade_certificate import PreTradeControlCertificate
from .certificates.certificate_status import CertificateStatus
from .certificates.certificate_scope import ConsumptionMode
from .certificates.certificate_errors import (
    CertificateExpiredError,
    CertificateRevokedError,
    CertificateReplayError,
    CertificateConsumptionError,
    CertificateUsageExhaustedError,
)


@dataclass
class CertificateLifecycle:
    """Manages the lifecycle of PreTradeControlCertificates.

    Orchestrates status transitions, consumption tracking, and usage recording.
    """

    # ── Certificates under management ─────────────────────────
    _active: Dict[str, PreTradeControlCertificate] = field(default_factory=dict)
    _used_ids: set = field(default_factory=set)

    # ── Recording ─────────────────────────────────────────────

    def register(self, cert: PreTradeControlCertificate) -> None:
        """Register a certificate for lifecycle management."""
        self._active[cert.certificate_id] = cert

    def deregister(self, cert_id: str) -> Optional[PreTradeControlCertificate]:
        """Remove a certificate from active management."""
        return self._active.pop(cert_id, None)

    # ── Lifecycle operations ──────────────────────────────────

    def activate(self, cert: PreTradeControlCertificate) -> PreTradeControlCertificate:
        """Activate a certificate (ISSUED → VALID)."""
        cert.activate()
        self.register(cert)
        return cert

    def consume(
        self,
        cert: PreTradeControlCertificate,
        quantity: float = 0.0,
        notional: float = 0.0,
    ) -> PreTradeControlCertificate:
        """Record consumption against the certificate's scope.

        For one-time certificates: marks as USED after consumption.
        For quantity-capped: tracks cumulative consumption, marks USED when exhausted.
        """
        # ── Pre-conditions ─────────────────────────────────
        # Check timestamp-based expiry first (cert may be ISSUED but past TTL)
        if cert.is_expired:
            raise CertificateExpiredError(
                cert.certificate_id, cert.issued_at,
                cert.expires_at or 0.0,
            )
        if cert.status == CertificateStatus.REVOKED:
            raise CertificateRevokedError(
                cert.certificate_id, cert.revocation_reason,
                cert.revoked_at or 0.0,
            )
        if cert.status == CertificateStatus.USED:
            raise CertificateUsageExhaustedError(cert.certificate_id)
        if not cert.is_active:
            if cert.status == CertificateStatus.EXPIRED:
                raise CertificateExpiredError(
                    cert.certificate_id, cert.issued_at,
                    cert.expires_at or 0.0,
                )
            raise CertificateUsageExhaustedError(cert.certificate_id)

        # ── Try consumption ────────────────────────────────
        if quantity > 0:
            try:
                cert.scope.consume_quantity(quantity)
            except ValueError as e:
                raise CertificateConsumptionError(
                    cert.certificate_id, "quantity", quantity,
                    cert.scope.quantity_remaining or 0.0,
                ) from e

        if notional > 0:
            try:
                cert.scope.consume_notional(notional)
            except ValueError as e:
                raise CertificateConsumptionError(
                    cert.certificate_id, "notional", notional,
                    cert.scope.notional_remaining or 0.0,
                ) from e

        # ── Post-consumption state transitions ─────────────
        mode = cert.scope.consumption_mode
        if mode == ConsumptionMode.ONE_TIME:
            cert.mark_used()
            self._used_ids.add(cert.certificate_id)
            self.deregister(cert.certificate_id)
        elif mode == ConsumptionMode.QUANTITY_CAPPED:
            remaining = cert.scope.quantity_remaining
            if remaining is not None and remaining <= 0:
                cert.mark_used()
                self._used_ids.add(cert.certificate_id)
                self.deregister(cert.certificate_id)
        elif mode == ConsumptionMode.NOTIONAL_CAPPED:
            remaining = cert.scope.notional_remaining
            if remaining is not None and remaining <= 0:
                cert.mark_used()
                self._used_ids.add(cert.certificate_id)
                self.deregister(cert.certificate_id)

        return cert

    def revoke(
        self, cert: PreTradeControlCertificate, reason: str
    ) -> PreTradeControlCertificate:
        """Revoke a certificate."""
        cert.revoke(reason)
        self.deregister(cert.certificate_id)
        return cert

    def expire(self, cert: PreTradeControlCertificate) -> PreTradeControlCertificate:
        """Expire a certificate."""
        cert.expire()
        self.deregister(cert.certificate_id)
        return cert

    # ── Queries ───────────────────────────────────────────────

    def is_replay(self, cert_id: str) -> bool:
        """Check whether a certificate ID has been seen as USED before."""
        return cert_id in self._used_ids

    def get_active(self) -> Dict[str, PreTradeControlCertificate]:
        """Get all currently active (VALID) certificates."""
        return dict(self._active)

    def get_certificate(self, cert_id: str) -> Optional[PreTradeControlCertificate]:
        """Get a certificate by ID."""
        return self._active.get(cert_id)

    def pending_expiry_check(self, now: Optional[float] = None) -> List[str]:
        """Check for expired certificates and expire them.

        Returns list of certificate IDs that were expired.
        """
        if now is None:
            now = time.time()
        expired_ids: List[str] = []
        for cert_id, cert in list(self._active.items()):
            if cert.is_expired:
                cert.expire()
                self.deregister(cert_id)
                expired_ids.append(cert_id)
        return expired_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_count": len(self._active),
            "used_count": len(self._used_ids),
            "active_ids": list(self._active.keys()),
        }
