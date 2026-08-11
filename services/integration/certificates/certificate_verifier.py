"""CertificateVerifier — runtime verification of certificate validity for a specific Order.

Unlike CertificateValidator (structural), the Verifier answers:
"Is this certificate currently usable for THIS specific order?"

It checks:
- Certificate is active (not expired, not revoked)
- Scope matches the order (symbol, side, venue, quantity, notional)
- Intent hash matches (order hasn't been modified since certificate issuance)
- Constraints are not violated
- Current control state is consistent
- Replay protection (one-time certificates already used)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .pre_trade_certificate import PreTradeControlCertificate
from .certificate_status import CertificateStatus
from .certificate_scope import ConsumptionMode


@dataclass
class CertificateVerificationResult:
    """Outcome of runtime certificate verification."""
    passed: bool = True
    certificate_id: str = ""
    order_intent_id: str = ""
    rejections: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    verified_at: float = field(default_factory=lambda: time.time())

    def add_rejection(self, reason: str) -> None:
        self.rejections.append(reason)
        self.passed = False

    def add_warning(self, reason: str) -> None:
        self.warnings.append(reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "certificate_id": self.certificate_id,
            "order_intent_id": self.order_intent_id,
            "rejections": self.rejections,
            "warnings": self.warnings,
            "verified_at": self.verified_at,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateVerificationResult(passed={self.passed}, "
            f"rejections={len(self.rejections)})"
        )


class CertificateVerifier:
    """Runtime verifier: is THIS certificate valid for THIS order RIGHT NOW?

    Unlike the Validator (structural), the Verifier checks contextual
    validity against a specific Order context.
    """

    def verify(
        self,
        cert: PreTradeControlCertificate,
        order_intent_id: str,
        intent_hash: str,
        symbol: str,
        side: str,
        quantity: float,
        notional: float = 0.0,
        venue: str = "",
        order_type: str = "",
        current_governance_state: str = "",
    ) -> CertificateVerificationResult:
        """Verify certificate for a specific order context.

        Returns a result with all rejections collected (not fail-fast).
        """
        result = CertificateVerificationResult(
            certificate_id=cert.certificate_id,
            order_intent_id=order_intent_id,
        )

        self._check_active(cert, result)
        self._check_order_intent_binding(cert, order_intent_id, result)
        self._check_intent_hash(cert, intent_hash, result)
        self._check_scope_symbol(cert, symbol, result)
        self._check_scope_side(cert, side, result)
        self._check_scope_venue(cert, venue, result)
        self._check_scope_quantity(cert, quantity, result)
        self._check_scope_notional(cert, notional, result)
        self._check_order_type(cert, order_type, result)
        self._check_replay(cert, result)
        self._check_governance_state(cert, current_governance_state, result)

        return result

    # ── Individual checks ─────────────────────────────────────

    def _check_active(
        self,
        cert: PreTradeControlCertificate,
        result: CertificateVerificationResult,
    ) -> None:
        """Certificate must be in an active status."""
        if cert.status.is_terminal:
            result.add_rejection(
                f"Certificate status is {cert.status.label} (terminal)"
            )
        if cert.is_expired:
            result.add_rejection(
                f"Certificate expired at {cert.expires_at}"
            )

    def _check_order_intent_binding(
        self,
        cert: PreTradeControlCertificate,
        order_intent_id: str,
        result: CertificateVerificationResult,
    ) -> None:
        """Certificate must be bound to the same order intent."""
        if cert.order_intent_id != order_intent_id:
            result.add_rejection(
                f"Order intent mismatch: cert={cert.order_intent_id[:20]}..., "
                f"order={order_intent_id[:20]}..."
            )

    def _check_intent_hash(
        self,
        cert: PreTradeControlCertificate,
        intent_hash: str,
        result: CertificateVerificationResult,
    ) -> None:
        """Intent hash must match — prevents 'approve then modify' attacks."""
        if cert.intent_hash and cert.intent_hash != intent_hash:
            result.add_rejection(
                f"Intent hash mismatch: cert={cert.intent_hash[:16]}..., "
                f"order={intent_hash[:16]}..."
            )

    def _check_scope_symbol(
        self,
        cert: PreTradeControlCertificate,
        symbol: str,
        result: CertificateVerificationResult,
    ) -> None:
        if not cert.scope.check_symbol(symbol):
            result.add_rejection(
                f"Symbol mismatch: scope={cert.scope.symbol}, "
                f"order={symbol}"
            )

    def _check_scope_side(
        self,
        cert: PreTradeControlCertificate,
        side: str,
        result: CertificateVerificationResult,
    ) -> None:
        if not cert.scope.check_side(side):
            result.add_rejection(
                f"Side mismatch: scope={cert.scope.side}, "
                f"order={side}"
            )

    def _check_scope_venue(
        self,
        cert: PreTradeControlCertificate,
        venue: str,
        result: CertificateVerificationResult,
    ) -> None:
        if venue and not cert.scope.check_venue(venue):
            result.add_rejection(
                f"Venue mismatch: scope={cert.scope.venue}, "
                f"order={venue}"
            )

    def _check_scope_quantity(
        self,
        cert: PreTradeControlCertificate,
        quantity: float,
        result: CertificateVerificationResult,
    ) -> None:
        if not cert.scope.check_quantity(quantity):
            result.add_rejection(
                f"Quantity exceeds scope: "
                f"requested={quantity}, remaining={cert.scope.quantity_remaining}"
            )

    def _check_scope_notional(
        self,
        cert: PreTradeControlCertificate,
        notional: float,
        result: CertificateVerificationResult,
    ) -> None:
        if notional > 0 and not cert.scope.check_notional(notional):
            result.add_rejection(
                f"Notional exceeds scope: "
                f"requested={notional}, remaining={cert.scope.notional_remaining}"
            )

    def _check_order_type(
        self,
        cert: PreTradeControlCertificate,
        order_type: str,
        result: CertificateVerificationResult,
    ) -> None:
        allowed = cert.scope.allowed_order_types
        if allowed and order_type and order_type.upper() not in [
            t.upper() for t in allowed
        ]:
            result.add_rejection(
                f"Order type '{order_type}' not in allowed: {allowed}"
            )

    def _check_replay(
        self,
        cert: PreTradeControlCertificate,
        result: CertificateVerificationResult,
    ) -> None:
        """Check replay protection for one-time certificates."""
        if cert.is_one_time and cert.status == CertificateStatus.USED:
            result.add_rejection(
                "One-time certificate has already been used"
            )

    def _check_governance_state(
        self,
        cert: PreTradeControlCertificate,
        current_governance_state: str,
        result: CertificateVerificationResult,
    ) -> None:
        """Check current governance state — certificate alone doesn't override.

        Historical approval does not equal current unconditional passage.
        """
        if current_governance_state == "FROZEN":
            result.add_rejection(
                "Current governance is FROZEN — certificate cannot authorize "
                "new action despite being valid"
            )
        if current_governance_state == "EMERGENCY":
            result.add_warning(
                "Current governance is EMERGENCY — risk of revocation"
            )
