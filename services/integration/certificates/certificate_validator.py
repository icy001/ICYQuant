"""CertificateValidator — structural and format validation for certificates.

Validates that a certificate is well-formed:
- Has required identifiers (certificate_id, flow_id, order_intent_id)
- Claims are present and properly structured
- Scope is valid
- Policy versions are recorded
- Signature and fingerprint are present

This is STRUCTURAL validation, not runtime verification (see CertificateVerifier).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .pre_trade_certificate import PreTradeControlCertificate
from .certificate_status import CertificateStatus
from .certificate_scope import CertificateScope


@dataclass
class ValidationError:
    """A single validation failure detail."""
    field: str = ""
    code: str = ""
    message: str = ""

    def __repr__(self) -> str:
        return f"ValidationError({self.field}: {self.code} - {self.message})"


@dataclass
class CertificateValidationReport:
    """Aggregated result of certificate validation."""
    valid: bool = True
    certificate_id: str = ""
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    validated_at: float = field(default_factory=lambda: time.time())

    def add_error(self, field: str, code: str, message: str) -> None:
        self.errors.append(
            ValidationError(field=field, code=code, message=message)
        )
        self.valid = False

    def add_warning(self, field: str, code: str, message: str) -> None:
        self.warnings.append(
            ValidationError(field=field, code=code, message=message)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "certificate_id": self.certificate_id,
            "errors": [
                {"field": e.field, "code": e.code, "message": e.message}
                for e in self.errors
            ],
            "warnings": [
                {"field": w.field, "code": w.code, "message": w.message}
                for w in self.warnings
            ],
            "validated_at": self.validated_at,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateValidationReport(valid={self.valid}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)})"
        )


class CertificateValidator:
    """Validates the structure and format of a PreTradeControlCertificate.

    This answers: "Is the certificate well-formed?"
    (Not: "Is the certificate currently usable for this order?" — that's the Verifier.)
    """

    def validate(self, cert: PreTradeControlCertificate) -> CertificateValidationReport:
        """Run all structural validations and return a report."""
        report = CertificateValidationReport(certificate_id=cert.certificate_id)

        self._validate_identity(cert, report)
        self._validate_lineage(cert, report)
        self._validate_claims(cert, report)
        self._validate_scope(cert, report)
        self._validate_policy_versions(cert, report)
        self._validate_evidence(cert, report)
        self._validate_integrity(cert, report)
        self._validate_status(cert, report)
        self._validate_timestamps(cert, report)

        return report

    # ── Individual checks ─────────────────────────────────────

    def _validate_identity(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if not cert.certificate_id:
            report.add_error("certificate_id", "MISSING_ID", "Certificate ID is empty")
        if not cert.order_intent_id:
            report.add_error(
                "order_intent_id", "MISSING_INTENT_ID",
                "Order intent ID is empty"
            )
        if not cert.flow_id:
            report.add_error("flow_id", "MISSING_FLOW_ID", "Flow ID is empty")

    def _validate_lineage(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if not cert.decision_id:
            report.add_warning(
                "decision_id", "MISSING_DECISION_ID",
                "Decision ID is empty — lineage may be incomplete"
            )
        if not cert.strategy_id:
            report.add_warning(
                "strategy_id", "MISSING_STRATEGY_ID",
                "Strategy ID is empty"
            )
        if not cert.account_id:
            report.add_error(
                "account_id", "MISSING_ACCOUNT_ID",
                "Account ID is empty"
            )

    def _validate_claims(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if cert.risk_claim is None:
            report.add_error(
                "risk_claim", "MISSING_CLAIM",
                "Risk claim is missing"
            )
        if cert.governance_claim is None:
            report.add_error(
                "governance_claim", "MISSING_CLAIM",
                "Governance claim is missing"
            )
        if cert.authority_claim is None:
            report.add_error(
                "authority_claim", "MISSING_CLAIM",
                "Authority claim is missing"
            )
        if cert.approval_claim is None:
            report.add_error(
                "approval_claim", "MISSING_CLAIM",
                "Approval claim is missing"
            )

    def _validate_scope(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        scope = cert.scope
        if not scope.symbol:
            report.add_error("scope.symbol", "MISSING_SYMBOL", "Scope symbol is empty")
        if not scope.side:
            report.add_error("scope.side", "MISSING_SIDE", "Scope side is empty")
        if scope.max_quantity is not None and scope.max_quantity <= 0:
            report.add_error(
                "scope.max_quantity", "INVALID_QUANTITY",
                f"Max quantity must be > 0, got {scope.max_quantity}"
            )

    def _validate_policy_versions(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if not cert.policy_versions:
            report.add_warning(
                "policy_versions", "NO_POLICY_VERSIONS",
                "No policy versions recorded — audit may be incomplete"
            )

    def _validate_evidence(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if not cert.evidence:
            report.add_warning(
                "evidence", "NO_EVIDENCE",
                "No evidence records — audit may be incomplete"
            )

    def _validate_integrity(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if cert.signature is None:
            report.add_error(
                "signature", "MISSING_SIGNATURE",
                "Certificate is not signed"
            )
        if cert.fingerprint is None:
            report.add_error(
                "fingerprint", "MISSING_FINGERPRINT",
                "Certificate fingerprint is missing"
            )

    def _validate_status(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if cert.status == CertificateStatus.INVALID:
            report.add_error(
                "status", "CERTIFICATE_INVALID",
                "Certificate is marked INVALID"
            )
        if cert.status == CertificateStatus.REVOKED:
            report.add_error(
                "status", "CERTIFICATE_REVOKED",
                "Certificate is revoked"
            )
        if cert.status == CertificateStatus.EXPIRED:
            report.add_error(
                "status", "CERTIFICATE_EXPIRED",
                "Certificate is expired"
            )

    def _validate_timestamps(
        self, cert: PreTradeControlCertificate, report: CertificateValidationReport
    ) -> None:
        if cert.issued_at <= 0:
            report.add_error(
                "issued_at", "INVALID_TIMESTAMP",
                "Issue timestamp is invalid"
            )
        if cert.expires_at is not None and cert.expires_at <= cert.issued_at:
            report.add_error(
                "expires_at", "INVALID_EXPIRY",
                "Expiry must be after issue time"
            )
