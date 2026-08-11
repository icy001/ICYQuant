"""
Certificate Manager — Manages TLS/SSL certificates for secure exchange
connectivity with trust store, rotation, and validation.

API Key → Secret → Signature → Token/Certificate → Authenticated Session
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CertificateType(str, Enum):
    CLIENT_CERT = "client_cert"
    CA_CERT = "ca_cert"
    COMBINED = "combined"


@dataclass
class Certificate:
    cert_id: str
    exchange_id: str
    cert_type: CertificateType
    cert_path: str
    key_path: str = ""
    passphrase: str = ""
    fingerprint: str = ""
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    issuer: str = ""
    subject: str = ""
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def days_until_expiry(self) -> int:
        if self.expires_at is None:
            return 365
        return max(0, (self.expires_at - datetime.now(timezone.utc)).days)


class CertificateManager:
    """
    Manages TLS/SSL certificates for secure exchange connectivity.

    Handles client certificates, CA certificates, trust store
    management, certificate rotation, and expiry monitoring.

    Usage::

        manager = CertificateManager()
        await manager.initialize()
        await manager.register(Certificate(
            "binance_client", "binance", CertificateType.CLIENT_CERT,
            cert_path="/certs/binance.crt", key_path="/certs/binance.key",
        ))
        cert = await manager.get("binance", CertificateType.CLIENT_CERT)
        is_valid = await manager.validate("binance_client")
    """

    def __init__(self, expiry_warning_days: int = 30) -> None:
        self.expiry_warning_days = expiry_warning_days
        self._certificates: dict[str, Certificate] = {}
        self._trust_store: dict[str, Certificate] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the certificate manager."""
        logger.info("CertificateManager initialized.")

    # ---- Certificate Management ----

    async def register(self, cert: Certificate) -> None:
        """Register a certificate."""
        async with self._lock:
            self._certificates[cert.cert_id] = cert
        logger.info("Certificate registered: %s for %s", cert.cert_id, cert.exchange_id)

        if cert.days_until_expiry <= self.expiry_warning_days:
            logger.warning(
                "Certificate %s expires in %d days!",
                cert.cert_id, cert.days_until_expiry,
            )

    async def get(
        self, exchange_id: str, cert_type: Optional[CertificateType] = None
    ) -> Optional[Certificate]:
        """Get a certificate for an exchange."""
        for cert in self._certificates.values():
            if cert.exchange_id == exchange_id and cert.is_active and not cert.is_expired:
                if cert_type is None or cert.cert_type == cert_type:
                    return cert
        return None

    async def get_by_id(self, cert_id: str) -> Optional[Certificate]:
        """Get a certificate by ID."""
        return self._certificates.get(cert_id)

    async def delete(self, cert_id: str) -> bool:
        """Delete a certificate."""
        async with self._lock:
            return self._certificates.pop(cert_id, None) is not None

    async def deactivate(self, cert_id: str) -> bool:
        """Deactivate a certificate."""
        cert = self._certificates.get(cert_id)
        if cert:
            cert.is_active = False
            return True
        return False

    async def validate(self, cert_id: str) -> bool:
        """Validate a certificate is active and not expired."""
        cert = self._certificates.get(cert_id)
        if cert is None:
            logger.error("Certificate not found: %s", cert_id)
            return False
        if not cert.is_active:
            logger.warning("Certificate %s is inactive", cert_id)
            return False
        if cert.is_expired:
            logger.error("Certificate %s is expired", cert_id)
            return False
        return True

    # ---- Trust Store ----

    async def add_trusted_ca(self, cert: Certificate) -> None:
        """Add a CA certificate to the trust store."""
        self._trust_store[cert.cert_id] = cert
        logger.info("CA certificate added to trust store: %s", cert.cert_id)

    async def remove_trusted_ca(self, cert_id: str) -> bool:
        """Remove a CA certificate from the trust store."""
        return self._trust_store.pop(cert_id, None) is not None

    async def get_trusted_ca(self, cert_id: str) -> Optional[Certificate]:
        """Get a trusted CA certificate."""
        return self._trust_store.get(cert_id)

    async def list_trusted_ca(self) -> list[Certificate]:
        """List all trusted CA certificates."""
        return list(self._trust_store.values())

    # ---- Expiry Monitoring ----

    async def get_expiring_soon(self) -> list[Certificate]:
        """Get certificates expiring within the warning threshold."""
        return [
            c for c in self._certificates.values()
            if c.is_active and c.days_until_expiry <= self.expiry_warning_days
        ]

    async def get_expired(self) -> list[Certificate]:
        """Get all expired certificates."""
        return [c for c in self._certificates.values() if c.is_expired]

    async def get_summary(self) -> dict[str, Any]:
        """Get certificate summary."""
        all_certs = list(self._certificates.values())
        active = sum(1 for c in all_certs if c.is_active and not c.is_expired)
        expiring = len(await self.get_expiring_soon())

        return {
            "total_certificates": len(all_certs),
            "active": active,
            "expired": sum(1 for c in all_certs if c.is_expired),
            "expiring_soon": expiring,
            "trust_store_size": len(self._trust_store),
            "certificates": [
                {
                    "cert_id": c.cert_id,
                    "exchange_id": c.exchange_id,
                    "days_until_expiry": c.days_until_expiry,
                    "is_expired": c.is_expired,
                    "is_active": c.is_active,
                }
                for c in all_certs
            ],
        }
