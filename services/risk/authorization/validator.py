"""Execution eligibility - the final authorization boundary before an order
request is admitted.

:class:`ExecutionEligibilityValidator` answers one question: does this
execution request match exactly what risk approved?  It checks identity,
scope, quantity ceiling, policy binding and expiration, and additionally
guards against authorization replay: one certificate may only ever produce
one order request identity.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from services.risk.authorization.scope import AuthorizationScope, scope_from_certificate

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.certificate import ExecutionAuthorizationCertificate


class AuthorizationViolation(str, Enum):
    """Machine-readable rejection reasons for the order request engine."""

    CERTIFICATE_EXPIRED = "CERTIFICATE_EXPIRED"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    STRATEGY_MISMATCH = "STRATEGY_MISMATCH"
    SESSION_MISMATCH = "SESSION_MISMATCH"
    SIGNAL_MISMATCH = "SIGNAL_MISMATCH"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    SIDE_MISMATCH = "SIDE_MISMATCH"
    QUANTITY_EXCEEDS_AUTHORIZATION = "QUANTITY_EXCEEDS_AUTHORIZATION"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    CORRELATION_MISMATCH = "CORRELATION_MISMATCH"


@dataclass(frozen=True)
class ExecutionRequest:
    """What the execution layer wants to do with a certificate.

    Quantity must never exceed the certificate's approved quantity and the
    identity fields must match the certificate exactly.
    """

    intent_id: str = ""
    strategy_id: str = ""
    session_id: str = ""
    signal_id: str = ""
    correlation_id: str = ""

    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    execution_policy: str = ""

    idempotency_key: str = ""


@dataclass(frozen=True)
class ExecutionEligibilityResult:
    """Verdict of one eligibility check."""

    eligible: bool
    reason: Optional[str] = None

    authorization_id: Optional[str] = None
    certificate_id: Optional[str] = None


@dataclass(frozen=True)
class AuthorizationConsumption:
    """Record of a certificate being consumed by one order request."""

    certificate_id: str
    authorization_id: str
    intent_id: str
    order_request_id: str

    consumed_at: float
    accepted: bool

    idempotency_key: Optional[str] = None
    reason: Optional[str] = None


class AuthorizationConsumer:
    """Replay protection ledger: one certificate -> one order request.

    Re-submitting the same ``order_request_id`` returns the original
    consumption record (idempotent retry); a different order request id on an
    already consumed certificate is refused.
    """

    def __init__(self, *, clock: Optional[float] = None) -> None:
        self._clock = clock if clock is not None else time.time()
        self._consumptions: dict[str, AuthorizationConsumption] = {}

    @property
    def consumptions(self) -> dict[str, AuthorizationConsumption]:
        """Read-only view of certificate_id -> consumption record."""
        return dict(self._consumptions)

    def consume(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        order_request_id: str,
        idempotency_key: Optional[str] = None,
        now: Optional[float] = None,
    ) -> AuthorizationConsumption:
        """Record that an order request consumes the certificate."""
        if not order_request_id:
            raise ValueError("order_request_id is required")
        reference = self._clock if now is None else now

        existing = self._consumptions.get(certificate.certificate_id)
        if existing is not None:
            if existing.order_request_id == order_request_id:
                return existing
            return AuthorizationConsumption(
                certificate_id=certificate.certificate_id,
                authorization_id=certificate.authorization_id,
                intent_id=certificate.intent_id,
                order_request_id=order_request_id,
                consumed_at=reference,
                accepted=False,
                idempotency_key=idempotency_key,
                reason="authorization_already_consumed",
            )

        record = AuthorizationConsumption(
            certificate_id=certificate.certificate_id,
            authorization_id=certificate.authorization_id,
            intent_id=certificate.intent_id,
            order_request_id=order_request_id,
            consumed_at=reference,
            accepted=True,
            idempotency_key=idempotency_key,
            reason=None,
        )
        self._consumptions[certificate.certificate_id] = record
        return record


class ExecutionEligibilityValidator:
    """Validates execution requests against an authorization certificate.

    Combines scope validation (identity / symbol / side / quantity ceiling /
    policy / expiration) with replay protection (one certificate may only
    produce one order request identity).
    """

    def __init__(
        self,
        *,
        clock: Optional[float] = None,
        consumer: Optional[AuthorizationConsumer] = None,
    ) -> None:
        self._clock = clock if clock is not None else time.time()
        self.consumer = consumer if consumer is not None else AuthorizationConsumer(clock=self._clock)

    def validate(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        execution_request: ExecutionRequest,
        *,
        now: Optional[float] = None,
    ) -> ExecutionEligibilityResult:
        """Check the request against the certificate's authorization scope."""
        reference = self._clock if now is None else now
        failure = self._first_violation(certificate, execution_request, reference)
        return ExecutionEligibilityResult(
            eligible=failure is None,
            reason=failure,
            authorization_id=certificate.authorization_id,
            certificate_id=certificate.certificate_id,
        )

    def consume(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        order_request_id: str,
        idempotency_key: Optional[str] = None,
        now: Optional[float] = None,
    ) -> AuthorizationConsumption:
        """Consume the certificate for one order request (replay safe)."""
        return self.consumer.consume(
            certificate,
            order_request_id=order_request_id,
            idempotency_key=idempotency_key,
            now=now,
        )

    def scope(self, certificate: "ExecutionAuthorizationCertificate") -> AuthorizationScope:
        """The authorization scope fixed by the certificate."""
        return scope_from_certificate(certificate)

    def _first_violation(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        request: ExecutionRequest,
        now: float,
    ) -> Optional[str]:
        if not certificate.approved:
            return "CERTIFICATE_REJECTED"
        if now >= certificate.expires_at:
            return AuthorizationViolation.CERTIFICATE_EXPIRED.value
        if request.intent_id != certificate.intent_id:
            return AuthorizationViolation.INTENT_MISMATCH.value
        if request.strategy_id != certificate.strategy_id:
            return AuthorizationViolation.STRATEGY_MISMATCH.value
        if request.session_id != certificate.session_id:
            return AuthorizationViolation.SESSION_MISMATCH.value
        if request.signal_id != certificate.signal_id:
            return AuthorizationViolation.SIGNAL_MISMATCH.value
        if request.symbol != certificate.symbol:
            return AuthorizationViolation.SYMBOL_MISMATCH.value
        if request.side != certificate.side:
            return AuthorizationViolation.SIDE_MISMATCH.value
        ceiling = certificate.approved_quantity or 0.0
        if request.quantity > ceiling:
            return AuthorizationViolation.QUANTITY_EXCEEDS_AUTHORIZATION.value
        if (
            certificate.execution_policy
            and request.execution_policy
            and request.execution_policy != certificate.execution_policy
        ):
            return AuthorizationViolation.POLICY_MISMATCH.value
        if (
            certificate.correlation_id
            and request.correlation_id
            and request.correlation_id != certificate.correlation_id
        ):
            return AuthorizationViolation.CORRELATION_MISMATCH.value
        return None
