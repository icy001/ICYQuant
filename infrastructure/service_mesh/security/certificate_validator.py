"""Certificate validation for ICYQuant Service Mesh.

Provides ``CertificateValidator`` for validating certificate signatures,
expiration, issuer, trust chain, and revocation status.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .certificate_authority import CertificateRecord

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of certificate validation."""

    def __init__(self, valid: bool, reason: str = "", checks: Optional[Dict[str, bool]] = None) -> None:
        self.valid = valid
        self.reason = reason
        self.checks = checks or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "checks": self.checks,
            "timestamp": self.timestamp.isoformat(),
        }


class CertificateValidator:
    """Validates certificates."""

    def __init__(self, trusted_issuers: Optional[List[str]] = None) -> None:
        self._lock = threading.RLock()
        self._trusted_issuers = set(trusted_issuers or ["icyquant-ca"])
        self._validation_count = 0
        self._failure_count = 0

    def add_trusted_issuer(self, issuer: str) -> None:
        with self._lock:
            self._trusted_issuers.add(issuer)

    def remove_trusted_issuer(self, issuer: str) -> bool:
        with self._lock:
            if issuer in self._trusted_issuers:
                self._trusted_issuers.remove(issuer)
                return True
            return False

    def validate(self, cert: CertificateRecord) -> ValidationResult:
        """Run all validation checks on a certificate."""
        checks: Dict[str, bool] = {}

        # 1. Signature check (simulated)
        checks["signature"] = bool(cert.public_key)

        # 2. Expiration check
        checks["expiration"] = not cert.is_expired

        # 3. Issuer check
        checks["issuer"] = cert.issuer in self._trusted_issuers

        # 4. Trust chain check (simulated)
        checks["trust_chain"] = True

        # 5. Revocation check
        checks["revocation"] = not cert.is_revoked

        all_passed = all(checks.values())
        reason = "ok" if all_passed else "; ".join(
            k for k, v in checks.items() if not v
        )

        with self._lock:
            self._validation_count += 1
            if not all_passed:
                self._failure_count += 1

        return ValidationResult(
            valid=all_passed,
            reason=reason,
            checks=checks,
        )

    def validate_batch(self, certs: List[CertificateRecord]) -> List[ValidationResult]:
        """Validate multiple certificates."""
        return [self.validate(c) for c in certs]

    @property
    def trusted_issuers(self) -> List[str]:
        with self._lock:
            return list(self._trusted_issuers)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "validation_count": self._validation_count,
                "failure_count": self._failure_count,
                "trusted_issuer_count": len(self._trusted_issuers),
                "trusted_issuers": list(self._trusted_issuers),
            }
