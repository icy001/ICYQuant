"""Authorization integration service - the single, hardened entry point.

Everything from Commit 31 (decision, certificate, scope validation,
eligibility, audit, idempotency, replay protection) is composed behind one
boundary::

    Authorization Request
        -> Risk Decision
        -> REJECTED / APPROVED
        -> Certificate (APPROVED only)
        -> Scope / Eligibility
        -> VERIFIED
        -> AuthorizedExecutionContext

:class:`AuthorizationIntegrationService.authorize` is the only way an execution
intent becomes an :class:`AuthorizedExecutionContext`.  The service is
fail-closed: any internal failure maps to ``INTEGRATION_FAILURE`` and never
produces an authorized context.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from services.risk.authorization.audit import AuthorizationAuditTrail
from services.risk.authorization.certificate import (
    AuthorizationCertificateIssuer,
    validate_certificate,
)
from services.risk.authorization.errors import (
    AuthorizationError,
    AuthorizationErrorCode,
    map_violation,
)
from services.risk.authorization.events import AuthorizationEventFactory
from services.risk.authorization.validator import ExecutionEligibilityValidator

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.certificate import ExecutionAuthorizationCertificate
    from services.risk.authorization.contract import RiskAuthorizationRequest
    from services.risk.authorization.decision import RiskDecision
    from services.risk.authorization.validator import ExecutionRequest

#: Callable that evaluates a risk authorization request into a risk decision.
RiskDecisionMaker = Callable[["RiskAuthorizationRequest"], "RiskDecision"]


@dataclass(frozen=True)
class AuthorizedExecutionContext:
    """Frozen proof that one trade is authorized to become an order request.

    This is NOT an order.  It is the input the Commit 32 order request engine
    consumes: the approved identity, scope and the quantity ceiling.
    """

    intent_id: str
    authorization_id: str
    certificate_id: str
    decision_id: str
    correlation_id: str

    strategy_id: str
    session_id: str
    signal_id: str

    symbol: str
    side: str

    approved_quantity: float


@dataclass(frozen=True)
class AuthorizationResult:
    """Unified outcome of an authorization call."""

    authorized: bool
    context: Optional[AuthorizedExecutionContext]
    reason: Optional[str] = None

    certificate_id: Optional[str] = None
    authorization_id: Optional[str] = None


class AuthorizationIntegrationService:
    """Composes risk authorization end-to-end behind one fail-closed boundary."""

    def __init__(
        self,
        *,
        decision_maker: RiskDecisionMaker,
        issuer: Optional[AuthorizationCertificateIssuer] = None,
        validator: Optional[ExecutionEligibilityValidator] = None,
        audit: Optional[AuthorizationAuditTrail] = None,
        events: Optional[AuthorizationEventFactory] = None,
        certificate_ttl_seconds: float = 5.0,
        clock: Optional[float] = None,
    ) -> None:
        self.decision_maker = decision_maker
        self.issuer = issuer if issuer is not None else AuthorizationCertificateIssuer()
        self.validator = validator if validator is not None else ExecutionEligibilityValidator()
        self.audit = audit if audit is not None else AuthorizationAuditTrail()
        self.events = events if events is not None else AuthorizationEventFactory()
        self.certificate_ttl_seconds = certificate_ttl_seconds
        self._clock = clock if clock is not None else time.time()

    # --- authorization entry point ------------------------------------------

    def authorize(self, request: "RiskAuthorizationRequest") -> AuthorizationResult:
        """Turn an authorization request into an authorized execution context.

        Rejected intents return ``authorized=False`` with ``RISK_REJECTED``;
        repeated calls for the same intent are idempotent and return the same
        authorization.  Any internal failure fails closed.
        """
        reference = self._now()
        self._audit(self.events.requested_from_request(request, occurred_at=reference))

        try:
            decision = self.decision_maker(request)
        except Exception as exc:  # noqa: BLE001 - fail closed on any risk failure
            return self._failure(
                AuthorizationErrorCode.INTEGRATION_FAILURE,
                "risk evaluation failed",
                detail=str(exc),
                correlation_id=request.correlation_id,
                occurred_at=reference,
            )

        if not decision.approved:
            self._audit(self.events.rejected_from_decision(decision, occurred_at=reference))
            return self._failure(
                AuthorizationErrorCode.RISK_REJECTED,
                "risk rejected the execution intent",
                detail=decision.reason,
                correlation_id=decision.correlation_id,
                occurred_at=reference,
            )

        self._audit(
            self.events.approved_from_decision(decision, occurred_at=reference)
        )

        try:
            certificate = self.issuer.issue(
                decision,
                strategy_id=decision.strategy_id,
                session_id=decision.session_id,
                signal_id=decision.signal_id,
                issued_at=reference,
                expires_at=reference + self.certificate_ttl_seconds,
            )
            validate_certificate(certificate, reference)
        except Exception as exc:  # noqa: BLE001 - fail closed on issuance errors
            return self._failure(
                AuthorizationErrorCode.INTEGRATION_FAILURE,
                "certificate issuance failed",
                detail=str(exc),
                correlation_id=decision.correlation_id,
                occurred_at=reference,
            )

        self._audit(self.events.issued_from_certificate(certificate, occurred_at=reference))

        context = AuthorizedExecutionContext(
            intent_id=certificate.intent_id,
            authorization_id=certificate.authorization_id,
            certificate_id=certificate.certificate_id,
            decision_id=certificate.decision_id,
            correlation_id=certificate.correlation_id,
            strategy_id=certificate.strategy_id,
            session_id=certificate.session_id,
            signal_id=certificate.signal_id,
            symbol=certificate.symbol,
            side=certificate.side,
            approved_quantity=certificate.approved_quantity or 0.0,
        )
        return AuthorizationResult(
            authorized=True,
            context=context,
            reason=None,
            certificate_id=certificate.certificate_id,
            authorization_id=certificate.authorization_id,
        )

    # --- certificate verification entry point --------------------------------

    def verify(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        execution_request: "ExecutionRequest",
        *,
        now: Optional[float] = None,
    ) -> AuthorizationResult:
        """Verify an existing certificate against an execution request.

        Returns an authorized context only when the request matches the
        certificate's authorization scope exactly.
        """
        reference = self._now() if now is None else now
        verdict = self.validator.validate(certificate, execution_request, now=reference)
        if verdict.eligible:
            self._audit(
                self.events.verified_from_certificate(certificate, occurred_at=reference)
            )
            context = AuthorizedExecutionContext(
                intent_id=certificate.intent_id,
                authorization_id=certificate.authorization_id,
                certificate_id=certificate.certificate_id,
                decision_id=certificate.decision_id,
                correlation_id=certificate.correlation_id,
                strategy_id=certificate.strategy_id,
                session_id=certificate.session_id,
                signal_id=certificate.signal_id,
                symbol=certificate.symbol,
                side=certificate.side,
                approved_quantity=certificate.approved_quantity or 0.0,
            )
            return AuthorizationResult(
                authorized=True,
                context=context,
                reason=None,
                certificate_id=certificate.certificate_id,
                authorization_id=certificate.authorization_id,
            )
        code = map_violation(verdict.reason or "")
        return self._failure(
            code,
            verdict.reason or "execution request not eligible",
            correlation_id=certificate.correlation_id,
            certificate_id=certificate.certificate_id,
            authorization_id=certificate.authorization_id,
            occurred_at=reference,
        )

    # --- consumption entry point ---------------------------------------------

    def consume(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        order_request_id: str,
        idempotency_key: Optional[str] = None,
        now: Optional[float] = None,
    ) -> AuthorizationResult:
        """Consume a certificate for one order request (replay safe)."""
        reference = self._now() if now is None else now
        consumption = self.validator.consume(
            certificate,
            order_request_id=order_request_id,
            idempotency_key=idempotency_key,
            now=reference,
        )
        if consumption.accepted:
            self._audit(
                self.events.consumed_from_certificate(
                    certificate,
                    order_request_id=order_request_id,
                    occurred_at=reference,
                )
            )
            return AuthorizationResult(
                authorized=True,
                context=AuthorizedExecutionContext(
                    intent_id=certificate.intent_id,
                    authorization_id=certificate.authorization_id,
                    certificate_id=certificate.certificate_id,
                    decision_id=certificate.decision_id,
                    correlation_id=certificate.correlation_id,
                    strategy_id=certificate.strategy_id,
                    session_id=certificate.session_id,
                    signal_id=certificate.signal_id,
                    symbol=certificate.symbol,
                    side=certificate.side,
                    approved_quantity=certificate.approved_quantity or 0.0,
                ),
                certificate_id=certificate.certificate_id,
                authorization_id=certificate.authorization_id,
            )
        return self._failure(
            AuthorizationErrorCode.ALREADY_CONSUMED,
            "authorization already consumed by another order request",
            detail=consumption.reason,
            correlation_id=certificate.correlation_id,
            certificate_id=certificate.certificate_id,
            authorization_id=certificate.authorization_id,
            occurred_at=reference,
        )

    # --- helpers -------------------------------------------------------------

    def _now(self) -> float:
        return self._clock

    def _audit(self, event) -> None:
        self.audit.append(event, actor="authorization-service")

    def _failure(
        self,
        code: AuthorizationErrorCode,
        message: str,
        *,
        detail: Optional[str] = None,
        correlation_id: Optional[str] = None,
        certificate_id: Optional[str] = None,
        authorization_id: Optional[str] = None,
        occurred_at: Optional[float] = None,
    ) -> AuthorizationResult:
        reference = self._now() if occurred_at is None else occurred_at
        # Record an audit trail of the failure for reconciliation to consume.
        if correlation_id:
            self._audit(
                self.events.rejected(
                    intent_id=correlation_id,
                    correlation_id=correlation_id,
                    occurred_at=reference,
                    reason=code.value,
                )
            )
        return AuthorizationResult(
            authorized=False,
            context=None,
            reason=code.value,
            certificate_id=certificate_id,
            authorization_id=authorization_id,
        )


def raise_authorization_error(code: AuthorizationErrorCode, message: str) -> None:
    """Raise a unified authorization boundary error."""
    raise AuthorizationError(code, message)
