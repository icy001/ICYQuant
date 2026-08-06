"""Certificate manager for ICYQuant Service Mesh.

Provides ``CertificateManager`` for managing the full certificate
lifecycle: issue, renew, rotate, revoke, and validate.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .certificate_authority import CertificateAuthority, CertificateRecord
from .certificate_store import CertificateStore
from .exceptions import CertificateError, CertificateExpiredError

logger = logging.getLogger(__name__)


class CertificateState(str):
    """Certificate lifecycle states."""

    ISSUED = "issued"
    ACTIVE = "active"
    RENEWING = "renewing"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class CertificateManager:
    """Manages certificate lifecycle."""

    def __init__(
        self,
        ca: Optional[CertificateAuthority] = None,
        store: Optional[CertificateStore] = None,
    ) -> None:
        self._ca = ca or CertificateAuthority()
        self._store = store or CertificateStore()
        self._lock = threading.RLock()
        self._renewal_threshold_hours = 6
        self._issue_count = 0
        self._renew_count = 0
        self._revoke_count = 0
        self._started = False

    @property
    def ca(self) -> CertificateAuthority:
        return self._ca

    @property
    def store(self) -> CertificateStore:
        return self._store

    async def issue(
        self,
        spiffe_id: str,
        cert_type: str = "workload",
        ttl_hours: int = 24,
        public_key: str = "",
    ) -> CertificateRecord:
        """Issue a new certificate."""
        cert = await self._ca.issue(
            spiffe_id=spiffe_id,
            cert_type=cert_type,
            ttl_hours=ttl_hours,
            public_key=public_key,
        )
        self._store.store(cert)
        with self._lock:
            self._issue_count += 1
        return cert

    async def renew(self, cert_id: str, ttl_hours: int = 24) -> CertificateRecord:
        """Renew a certificate (extend TTL without revoking)."""
        cert = self._store.get(cert_id)
        if not cert:
            raise CertificateError(f"Certificate not found: {cert_id}")
        cert.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        cert.status = "active"
        with self._lock:
            self._renew_count += 1
        logger.info("Certificate renewed: %s", cert_id)
        return cert

    async def rotate(self, cert_id: str, ttl_hours: int = 24) -> CertificateRecord:
        """Rotate a certificate (revoke old, issue new)."""
        old_cert = self._store.get(cert_id)
        if not old_cert:
            raise CertificateError(f"Certificate not found: {cert_id}")
        new_cert = await self._ca.rotate(cert_id, ttl_hours=ttl_hours)
        self._store.store(new_cert)
        with self._lock:
            self._renew_count += 1
        return new_cert

    async def revoke(self, cert_id: str, reason: str = "") -> bool:
        """Revoke a certificate."""
        result = await self._ca.revoke(cert_id, reason)
        if result:
            cert = self._store.get(cert_id)
            if cert:
                cert.status = "revoked"
            with self._lock:
                self._revoke_count += 1
        return result

    def validate(self, cert_id: str) -> Dict[str, Any]:
        """Validate a certificate."""
        cert = self._store.get(cert_id)
        if not cert:
            return {"valid": False, "reason": "not_found"}
        if cert.is_revoked:
            return {"valid": False, "reason": "revoked"}
        if cert.is_expired:
            return {"valid": False, "reason": "expired"}
        return {"valid": True, "reason": "ok", "cert": cert.to_dict()}

    def get_certificate(self, cert_id: str) -> Optional[CertificateRecord]:
        return self._store.get(cert_id)

    def list_certificates(self) -> List[CertificateRecord]:
        return self._store.list_all()

    def get_expiring_soon(self, hours: int = 6) -> List[CertificateRecord]:
        """Get certificates expiring within the given hours."""
        threshold = datetime.utcnow() + timedelta(hours=hours)
        return [
            c for c in self._store.list_all()
            if c.is_active and c.expires_at <= threshold
        ]

    def start(self) -> None:
        self._ca.start()
        self._started = True

    def stop(self) -> None:
        self._ca.stop()
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started": self._started,
                "issue_count": self._issue_count,
                "renew_count": self._renew_count,
                "revoke_count": self._revoke_count,
                "ca": self._ca.get_stats(),
                "store": self._store.get_stats(),
            }
