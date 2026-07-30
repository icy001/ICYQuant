"""
ICYQuant Certificate Manager

TLS certificate lifecycle management with automatic rotation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import base64

logger = logging.getLogger(__name__)


class CertificateType(str, Enum):
    ROOT_CA = "root_ca"
    INTERMEDIATE_CA = "intermediate_ca"
    SERVER = "server"
    CLIENT = "client"
    CODE_SIGNING = "code_signing"


class CertificateStatus(str, Enum):
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_ROTATION = "pending_rotation"


@dataclass
class Certificate:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""
    type: CertificateType = CertificateType.SERVER
    status: CertificateStatus = CertificateStatus.VALID
    issuer: str = ""
    serial_number: str = ""
    not_before: datetime = field(default_factory=datetime.now)
    not_after: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=365))
    thumbprint: str = ""
    pem_certificate: str = ""
    pem_private_key: str = ""
    dns_names: List[str] = field(default_factory=list)
    ip_addresses: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    def needs_rotation(self, days_before: int = 30) -> bool:
        if self.status == CertificateStatus.EXPIRED:
            return True
        threshold = self.not_after - timedelta(days=days_before)
        return datetime.now() >= threshold

    def days_until_expiry(self) -> int:
        delta = self.not_after - datetime.now()
        return delta.days

    def revoke(self):
        self.status = CertificateStatus.REVOKED

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "subject": self.subject,
            "type": self.type.value,
            "status": self.status.value,
            "issuer": self.issuer,
            "notBefore": self.not_before.isoformat(),
            "notAfter": self.not_after.isoformat(),
            "needsRotation": self.needs_rotation(),
            "daysUntilExpiry": self.days_until_expiry(),
            "dnsNames": self.dns_names,
        }


class CertificateManager:
    """
    TLS certificate lifecycle management.

    Handles certificate issuance, rotation, revocation, and monitoring.
    Supports automatic rotation before expiration.
    """

    def __init__(self):
        self._certificates: Dict[str, Certificate] = {}
        self._ca_certificates: Dict[str, Certificate] = {}
        self._rotation_log: List[Dict] = []

    def issue_certificate(
        self,
        subject: str,
        cert_type: CertificateType = CertificateType.SERVER,
        validity_days: int = 365,
        dns_names: Optional[List[str]] = None,
        ip_addresses: Optional[List[str]] = None,
        issuer: str = "icyquant-ca",
    ) -> Certificate:
        cert = Certificate(
            subject=subject,
            type=cert_type,
            issuer=issuer,
            dns_names=dns_names or [],
            ip_addresses=ip_addresses or [],
            serial_number=uuid.uuid4().hex.upper(),
            not_before=datetime.now(),
            not_after=datetime.now() + timedelta(days=validity_days),
            thumbprint=uuid.uuid4().hex,
        )

        self._certificates[cert.id] = cert
        if cert_type in (CertificateType.ROOT_CA, CertificateType.INTERMEDIATE_CA):
            self._ca_certificates[cert.id] = cert

        logger.info(f"Certificate issued: {subject} ({cert_type.value})")
        return cert

    def get_certificate(self, cert_id: str) -> Optional[Certificate]:
        return self._certificates.get(cert_id)

    def revoke_certificate(self, cert_id: str):
        cert = self._certificates.get(cert_id)
        if cert:
            cert.revoke()
            logger.info(f"Certificate revoked: {cert.subject}")

    def rotate_certificate(self, cert_id: str) -> Optional[Certificate]:
        cert = self._certificates.get(cert_id)
        if not cert:
            return None

        new_cert = self.issue_certificate(
            subject=cert.subject,
            cert_type=cert.type,
            validity_days=(cert.not_after - cert.not_before).days,
            dns_names=cert.dns_names,
            ip_addresses=cert.ip_addresses,
            issuer=cert.issuer,
        )

        cert.revoke()
        self._rotation_log.append({
            "oldCertId": cert_id,
            "newCertId": new_cert.id,
            "subject": cert.subject,
            "rotatedAt": datetime.now().isoformat(),
        })

        logger.info(f"Certificate rotated: {cert.subject}")
        return new_cert

    def get_rotation_candidates(self, days_before: int = 30) -> List[Certificate]:
        return [
            cert for cert in self._certificates.values()
            if cert.status == CertificateStatus.VALID and cert.needs_rotation(days_before)
        ]

    def list_certificates(
        self,
        cert_type: Optional[CertificateType] = None,
        status: Optional[CertificateStatus] = None,
    ) -> List[Certificate]:
        certs = list(self._certificates.values())
        if cert_type:
            certs = [c for c in certs if c.type == cert_type]
        if status:
            certs = [c for c in certs if c.status == status]
        return certs

    def check_expiry(self) -> Dict:
        now = datetime.now()
        results = {
            "expired": [],
            "expiring_soon": [],
            "valid": [],
        }
        for cert in self._certificates.values():
            days = cert.days_until_expiry()
            if days < 0:
                results["expired"].append({"id": cert.id, "subject": cert.subject, "days": days})
            elif days < 30:
                results["expiring_soon"].append({"id": cert.id, "subject": cert.subject, "days": days})
            else:
                results["valid"].append({"id": cert.id, "subject": cert.subject, "days": days})
        return results

    def bulk_rotate(self) -> List[Dict]:
        candidates = self.get_rotation_candidates()
        results = []
        for cert in candidates:
            new_cert = self.rotate_certificate(cert.id)
            results.append({
                "subject": cert.subject,
                "oldCertId": cert.id,
                "newCertId": new_cert.id if new_cert else None,
            })
        return results

    def to_dict(self) -> Dict:
        return {
            "totalCertificates": len(self._certificates),
            "validCount": sum(1 for c in self._certificates.values() if c.status == CertificateStatus.VALID),
            "expiredCount": sum(1 for c in self._certificates.values() if c.status == CertificateStatus.EXPIRED),
            "rotationCandidates": len(self.get_rotation_candidates()),
        }
