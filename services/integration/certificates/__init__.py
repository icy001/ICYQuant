"""Pre-Trade Control Certificate package.

Provides the full certificate lifecycle:
- PreTradeControlCertificate — immutable proof of pre-trade control pass
- CertificateBuilder — assemble evidence into a certificate
- CertificateValidator — structural/format validation
- CertificateVerifier — runtime scope + constraint verification
"""

from __future__ import annotations


def __getattr__(name: str):
    """Lazy-load submodules to avoid circular imports during bootstrap."""
    _imports = {
        "CertificateStatus": ".certificate_status",
        "CertificateScope": ".certificate_scope",
        "CertificateClaim": ".certificate_claim",
        "CertificateEvidence": ".certificate_evidence",
        "EvidenceKind": ".certificate_evidence",
        "CertificateSignature": ".certificate_signature",
        "CertificateFingerprint": ".certificate_fingerprint",
        "PreTradeControlCertificate": ".pre_trade_certificate",
        "CertificateBuilder": ".certificate_builder",
        "CertificateValidator": ".certificate_validator",
        "CertificateValidationReport": ".certificate_validator",
        "CertificateVerifier": ".certificate_verifier",
        "CertificateVerificationResult": ".certificate_verifier",
        "CertificateError": ".certificate_errors",
        "CertificateExpiredError": ".certificate_errors",
        "CertificateRevokedError": ".certificate_errors",
        "CertificateScopeViolationError": ".certificate_errors",
        "CertificateIntegrityError": ".certificate_errors",
        "CertificateReplayError": ".certificate_errors",
        "CertificateConsumptionError": ".certificate_errors",
        "CertificateUsageExhaustedError": ".certificate_errors",
    }
    if name in _imports:
        import importlib
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PreTradeControlCertificate",
    "CertificateBuilder",
    "CertificateValidator",
    "CertificateValidationReport",
    "CertificateVerifier",
    "CertificateVerificationResult",
    "CertificateStatus",
    "CertificateScope",
    "CertificateClaim",
    "CertificateEvidence",
    "EvidenceKind",
    "CertificateSignature",
    "CertificateFingerprint",
    "CertificateError",
    "CertificateExpiredError",
    "CertificateRevokedError",
    "CertificateScopeViolationError",
    "CertificateIntegrityError",
    "CertificateReplayError",
    "CertificateConsumptionError",
    "CertificateUsageExhaustedError",
]
