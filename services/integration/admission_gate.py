"""AdmissionGate — the final gate that certifies an order is ready for OMS.

After all admission checks pass, the AdmissionGate produces a signed
OrderCertificate. OMS must reject any order without a valid certificate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_intent import OrderIntent
from .order_constraints import OrderConstraints
from .order_certificate import OrderCertificate, CertificateStatus
from .order_fingerprint import OrderFingerprint
from .admission_context import AdmissionContext
from .admission_result import AdmissionResult


@dataclass
class GateResult:
    """Result from the admission gate check."""
    passed: bool = True
    certificate: Optional[OrderCertificate] = None
    code: str = ""
    message: str = ""

    @classmethod
    def pass_through(cls, certificate: OrderCertificate) -> "GateResult":
        return cls(
            passed=True,
            certificate=certificate,
            code="GATE_PASS",
            message="Certificate valid, order admitted to OMS",
        )

    @classmethod
    def reject(cls, code: str, message: str) -> "GateResult":
        return cls(passed=False, code=code, message=message)


@dataclass
class AdmissionGate:
    """Final gate between admission and OMS.

    Issues certificates and validates them before OMS entry.
    The gate enforces that:
    1. Every admitted order has a valid certificate
    2. Certificate hashes match the order data
    3. Certificate has not expired
    4. Certificate has not been tampered with
    """

    certificate_ttl_seconds: float = 300.0

    def issue_certificate(
        self,
        intent: OrderIntent,
        constraints: OrderConstraints,
        result: AdmissionResult,
        context: AdmissionContext,
        fingerprint: str,
    ) -> OrderCertificate:
        """Issue a certificate for an admitted order."""
        versions = {
            "policy": context.policy_version,
            "risk": context.risk_version,
            "governance": context.governance_version,
            "authority": context.authority_version,
            "approval": context.approval_version,
        }

        certificate = OrderCertificate.create(
            intent=intent.to_dict(),
            constraints=constraints.to_dict(),
            policy={},
            fingerprint=fingerprint,
            flow_id=result.flow_id,
            decision_id=context.decision_id,
            order_id=result.order_id,
            authority_id=context.authority_id,
            approval_id=context.approval_id,
            versions=versions,
            ttl_seconds=self.certificate_ttl_seconds,
        )

        return certificate

    def validate_for_oms(
        self, certificate: OrderCertificate, intent: OrderIntent
    ) -> GateResult:
        """Validate a certificate before OMS accepts the order.

        This is called by OMS when receiving an order with a certificate.
        The OMS MUST check certificate validity before accepting.
        """
        # Check certificate status
        status = certificate.validate()
        if status == CertificateStatus.EXPIRED:
            return GateResult.reject(
                "CERTIFICATE_EXPIRED",
                "Certificate has expired",
            )
        if status == CertificateStatus.REVOKED:
            return GateResult.reject(
                "CERTIFICATE_REVOKED",
                "Certificate has been revoked",
            )
        if status == CertificateStatus.TAMPERED:
            return GateResult.reject(
                "CERTIFICATE_TAMPERED",
                "Certificate integrity check failed",
            )

        # Verify intent hash matches
        if not certificate.verify_intent(intent.to_dict()):
            return GateResult.reject(
                "CERTIFICATE_MISMATCH",
                "Order intent does not match certificate — order may have been modified",
            )

        return GateResult.pass_through(certificate)

    def __repr__(self) -> str:
        return f"AdmissionGate(ttl={self.certificate_ttl_seconds}s)"
