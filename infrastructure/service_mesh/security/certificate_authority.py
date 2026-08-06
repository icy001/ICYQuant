"""Certificate Authority for ICYQuant Service Mesh.

Provides ``CertificateAuthority`` for issuing, revoking, and rotating
mesh certificates. Supports internal CA with external CA reserved.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .exceptions import CertificateIssueError, CertificateRevocationError

logger = logging.getLogger(__name__)


class CertificateType(str):
    """Certificate types."""

    CA = "ca"
    INTERMEDIATE = "intermediate"
    WORKLOAD = "workload"
    CLIENT = "client"
    SERVER = "server"


class CertificateRecord:
    """A certificate record managed by the CA."""

    def __init__(
        self,
        cert_id: str,
        spiffe_id: str,
        cert_type: str = "workload",
        issuer: str = "icyquant-ca",
        serial_number: str = "",
        valid_from: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        public_key: str = "",
        private_key_id: str = "",
        status: str = "active",
    ) -> None:
        self.cert_id = cert_id
        self.spiffe_id = spiffe_id
        self.cert_type = cert_type
        self.issuer = issuer
        self.serial_number = serial_number or cert_id
        self.valid_from = valid_from or datetime.utcnow()
        self.expires_at = expires_at or (datetime.utcnow() + timedelta(hours=24))
        self.public_key = public_key
        self.private_key_id = private_key_id
        self.status = status
        self.created_at = datetime.utcnow()
        self.revoked_at: Optional[datetime] = None
        self.revocation_reason: str = ""

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.status == "revoked"

    @property
    def is_active(self) -> bool:
        return self.status == "active" and not self.is_expired

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cert_id": self.cert_id,
            "spiffe_id": self.spiffe_id,
            "cert_type": self.cert_type,
            "issuer": self.issuer,
            "serial_number": self.serial_number,
            "valid_from": self.valid_from.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "public_key": self.public_key,
            "private_key_id": self.private_key_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revocation_reason": self.revocation_reason,
            "is_expired": self.is_expired,
            "is_revoked": self.is_revoked,
            "is_active": self.is_active,
        }


class CertificateAuthority:
    """Internal Certificate Authority for the mesh."""

    def __init__(
        self,
        ca_id: str = "icyquant-ca",
        trust_domain: str = "icyquant.local",
        root_cert: str = "",
    ) -> None:
        self.ca_id = ca_id
        self.trust_domain = trust_domain
        self.root_cert = root_cert or f"root-cert-{ca_id}"
        self._lock = threading.RLock()
        self._certificates: Dict[str, CertificateRecord] = {}
        self._serial_counter = 0
        self._issue_count = 0
        self._revoke_count = 0
        self._started = False

    async def issue(
        self,
        spiffe_id: str,
        cert_type: str = "workload",
        ttl_hours: int = 24,
        public_key: str = "",
        private_key_id: str = "",
    ) -> CertificateRecord:
        """Issue a new certificate."""
        with self._lock:
            self._serial_counter += 1
            cert_id = f"cert-{self._serial_counter:06d}"
            serial_number = hashlib.sha256(
                f"{cert_id}:{spiffe_id}:{time.time()}".encode()
            ).hexdigest()[:32]

        cert = CertificateRecord(
            cert_id=cert_id,
            spiffe_id=spiffe_id,
            cert_type=cert_type,
            issuer=self.ca_id,
            serial_number=serial_number,
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
            public_key=public_key or f"pub-{cert_id}",
            private_key_id=private_key_id or f"key-{cert_id}",
        )

        with self._lock:
            self._certificates[cert_id] = cert
            self._issue_count += 1

        logger.info("Certificate issued: %s for %s", cert_id, spiffe_id)
        return cert

    async def revoke(self, cert_id: str, reason: str = "") -> bool:
        """Revoke a certificate."""
        with self._lock:
            cert = self._certificates.get(cert_id)
            if not cert:
                raise CertificateRevocationError(f"Certificate not found: {cert_id}")
            if cert.is_revoked:
                return True
            cert.status = "revoked"
            cert.revoked_at = datetime.utcnow()
            cert.revocation_reason = reason
            self._revoke_count += 1

        logger.warning("Certificate revoked: %s (reason: %s)", cert_id, reason)
        return True

    async def rotate(self, cert_id: str, ttl_hours: int = 24) -> CertificateRecord:
        """Rotate a certificate by revoking the old and issuing a new one."""
        with self._lock:
            old_cert = self._certificates.get(cert_id)
        if not old_cert:
            raise CertificateIssueError(f"Certificate not found: {cert_id}")

        await self.revoke(cert_id, "rotation")
        new_cert = await self.issue(
            spiffe_id=old_cert.spiffe_id,
            cert_type=old_cert.cert_type,
            ttl_hours=ttl_hours,
            public_key=old_cert.public_key,
            private_key_id=old_cert.private_key_id,
        )
        logger.info("Certificate rotated: %s -> %s", cert_id, new_cert.cert_id)
        return new_cert

    def get_certificate(self, cert_id: str) -> Optional[CertificateRecord]:
        with self._lock:
            return self._certificates.get(cert_id)

    def get_by_spiffe_id(self, spiffe_id: str) -> List[CertificateRecord]:
        with self._lock:
            return [c for c in self._certificates.values() if c.spiffe_id == spiffe_id]

    def list_certificates(self, status: Optional[str] = None) -> List[CertificateRecord]:
        with self._lock:
            certs = list(self._certificates.values())
        if status:
            certs = [c for c in certs if c.status == status]
        return certs

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            active = sum(1 for c in self._certificates.values() if c.is_active)
            return {
                "ca_id": self.ca_id,
                "trust_domain": self.trust_domain,
                "total_certificates": len(self._certificates),
                "active_certificates": active,
                "issue_count": self._issue_count,
                "revoke_count": self._revoke_count,
                "started": self._started,
            }
