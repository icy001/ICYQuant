"""CertificateErrors — domain-specific error types for certificate lifecycle.

Each error class maps to a specific invariant violation:
- Expired → certificate TTL exceeded
- Revoked → certificate actively revoked
- ScopeViolation → order outside certificate scope
- IntegrityError → hash/fingerprint mismatch (tampering)
- ReplayError → duplicate use of one-time certificate
- ConsumptionError → quantity/notional exhaustion
"""

from __future__ import annotations


class CertificateError(Exception):
    """Base exception for all certificate domain errors."""

    def __init__(self, message: str, certificate_id: str = "", code: str = "") -> None:
        super().__init__(message)
        self.certificate_id = certificate_id
        self.code = code


class CertificateExpiredError(CertificateError):
    """Certificate TTL has elapsed. Cannot authorize further actions."""

    def __init__(self, certificate_id: str, issued_at: float, expires_at: float) -> None:
        super().__init__(
            message=(
                f"Certificate {certificate_id} expired: "
                f"issued={issued_at:.0f}, expired={expires_at:.0f}"
            ),
            certificate_id=certificate_id,
            code="CERTIFICATE_EXPIRED",
        )
        self.issued_at = issued_at
        self.expires_at = expires_at


class CertificateRevokedError(CertificateError):
    """Certificate has been actively revoked. Cannot authorize any actions."""

    def __init__(
        self, certificate_id: str, reason: str, revoked_at: float = 0.0
    ) -> None:
        super().__init__(
            message=f"Certificate {certificate_id} revoked: {reason}",
            certificate_id=certificate_id,
            code="CERTIFICATE_REVOKED",
        )
        self.reason = reason
        self.revoked_at = revoked_at


class CertificateScopeViolationError(CertificateError):
    """Order exceeds certificate scope (symbol, side, quantity, venue, etc.)."""

    def __init__(
        self, certificate_id: str, field: str, expected: str, actual: str
    ) -> None:
        super().__init__(
            message=(
                f"Certificate {certificate_id} scope violation on '{field}': "
                f"expected '{expected}', got '{actual}'"
            ),
            certificate_id=certificate_id,
            code="CERTIFICATE_SCOPE_VIOLATION",
        )
        self.field = field
        self.expected_value = expected
        self.actual_value = actual


class CertificateIntegrityError(CertificateError):
    """Certificate fingerprint/hash mismatch. Evidence of tampering."""

    def __init__(
        self, certificate_id: str, expected_hash: str, actual_hash: str
    ) -> None:
        super().__init__(
            message=(
                f"Certificate {certificate_id} integrity check failed: "
                f"expected={expected_hash[:16]}..., actual={actual_hash[:16]}..."
            ),
            certificate_id=certificate_id,
            code="CERTIFICATE_INTEGRITY_FAILURE",
        )
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class CertificateReplayError(CertificateError):
    """Duplicate use of a one-time (or already-used) certificate detected."""

    def __init__(self, certificate_id: str) -> None:
        super().__init__(
            message=f"Certificate {certificate_id} replay detected (already USED)",
            certificate_id=certificate_id,
            code="CERTIFICATE_REPLAY_DETECTED",
        )


class CertificateConsumptionError(CertificateError):
    """Quantity or notional consumption has exceeded certificate max."""

    def __init__(
        self,
        certificate_id: str,
        metric: str,
        requested: float,
        remaining: float,
    ) -> None:
        super().__init__(
            message=(
                f"Certificate {certificate_id} {metric} consumption: "
                f"requested={requested}, remaining={remaining}"
            ),
            certificate_id=certificate_id,
            code="CERTIFICATE_CONSUMPTION_EXCEEDED",
        )
        self.metric = metric
        self.requested = requested
        self.remaining = remaining


class CertificateUsageExhaustedError(CertificateError):
    """Certificate has been fully consumed (USED) and cannot be reused."""

    def __init__(self, certificate_id: str) -> None:
        super().__init__(
            message=f"Certificate {certificate_id} usage exhausted",
            certificate_id=certificate_id,
            code="CERTIFICATE_USAGE_EXHAUSTED",
        )
