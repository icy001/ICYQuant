"""Execution authorization certificate - the formal authorization evidence.

A :class:`RiskDecision` is the risk engine's verdict; an
:class:`ExecutionAuthorizationCertificate` is the frozen proof that the trade
chain may continue::

    Risk Decision
        -> Execution Authorization
        -> Authorization Certificate
        -> Certificate Verification
        -> Order Request

The certificate fixes the authorization scope (strategy / session / signal /
intent / symbol / side / approved_quantity), the TTL window (``issued_at`` /
``expires_at``) and the full lineage ids.  It is immutable: changing an
approval means re-running risk evaluation and issuing a brand new certificate.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from services.risk.authorization.contract import ExecutionAuthorization, new_authorization_id

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.decision import RiskDecision


@dataclass(frozen=True)
class ExecutionAuthorizationCertificate:
    """Immutable authorization evidence that gates order requests.

    ``approved`` + ``issued_at`` / ``expires_at`` define the validity window:
    APPROVED and ``now < expires_at`` means VALID, otherwise EXPIRED.  A
    certificate with ``approved=False`` is REJECTED and can never be issued.
    """

    certificate_id: str
    authorization_id: str
    decision_id: str
    intent_id: str

    strategy_id: str
    session_id: str
    signal_id: str

    correlation_id: str

    approved: bool
    approved_quantity: Optional[float]

    issued_at: float
    expires_at: float

    symbol: str = ""
    side: str = ""
    execution_policy: Optional[str] = None
    reason: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        """Audit-ready plain mapping of the certificate."""
        return {
            "certificate_id": self.certificate_id,
            "authorization_id": self.authorization_id,
            "decision_id": self.decision_id,
            "intent_id": self.intent_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "approved": self.approved,
            "approved_quantity": self.approved_quantity,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "symbol": self.symbol,
            "side": self.side,
            "execution_policy": self.execution_policy,
            "reason": self.reason,
        }


_certificate_counter = itertools.count(1)


def new_certificate_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic certificate id.

    Example: ``CERT-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_certificate_counter)
    return f"CERT-{date_part}-{sequence:06d}"


def certificate_expired(
    certificate: "ExecutionAuthorizationCertificate",
    now: float,
) -> bool:
    """Return True when the certificate TTL window has closed."""
    return now >= certificate.expires_at


def validate_certificate(
    certificate: "ExecutionAuthorizationCertificate",
    now: float,
) -> None:
    """Core certificate checks (approved / TTL / approved quantity)."""
    if not certificate.approved:
        raise ValueError("authorization is not approved")
    if now >= certificate.expires_at:
        raise ValueError("authorization certificate expired")
    if certificate.approved_quantity is None:
        raise ValueError("approved quantity is required")


def verify_binding(
    certificate: "ExecutionAuthorizationCertificate",
    intent_id: str,
    correlation_id: str,
) -> None:
    """Bind the certificate to one intent and one correlation chain."""
    if certificate.intent_id != intent_id:
        raise ValueError("certificate intent mismatch")
    if certificate.correlation_id != correlation_id:
        raise ValueError("certificate correlation mismatch")


class AuthorizationCertificateIssuer:
    """Issues immutable certificates from risk decisions (idempotent).

    One risk decision can produce exactly one certificate; one intent gets the
    same certificate back while it is still valid (replay / double
    authorization protection).  An expired certificate does NOT block a fresh
    risk evaluation: a new decision simply produces a new certificate.
    """

    def __init__(self, *, clock: Optional[float] = None) -> None:
        self._clock = clock if clock is not None else time.time()
        #: decision_id -> certificate (1:1, a decision can never authorize twice).
        self._by_decision: dict[str, ExecutionAuthorizationCertificate] = {}
        #: intent_id -> certificate (replay protection per intent).
        self._by_intent: dict[str, ExecutionAuthorizationCertificate] = {}

    @property
    def certificates(self) -> dict[str, ExecutionAuthorizationCertificate]:
        """Read-only view of decision_id -> certificate."""
        return dict(self._by_decision)

    def issue(
        self,
        decision: "RiskDecision",
        *,
        strategy_id: str,
        session_id: str,
        signal_id: str,
        issued_at: float,
        expires_at: float,
    ) -> ExecutionAuthorizationCertificate:
        """Issue a certificate for an approved, well-formed decision."""
        if not decision.approved:
            raise ValueError("cannot issue certificate for rejected decision")
        if not decision.decision_id:
            raise ValueError("decision_id is required")
        if not decision.intent_id:
            raise ValueError("intent_id is required")
        if not decision.correlation_id:
            raise ValueError("correlation_id is required")
        if not strategy_id or not session_id or not signal_id:
            raise ValueError("strategy_id, session_id and signal_id are required")
        for attribute, value in (
            ("strategy_id", strategy_id),
            ("session_id", session_id),
            ("signal_id", signal_id),
        ):
            decided = getattr(decision, attribute, None)
            if decided and decided != value:
                raise ValueError(f"decision identity mismatch: {attribute}")
        if decision.approved_quantity is None or decision.approved_quantity <= 0:
            raise ValueError("approved quantity must be positive")
        if expires_at <= issued_at:
            raise ValueError("certificate expires_at must be after issued_at")

        existing = self._by_decision.get(decision.decision_id)
        if existing is not None:
            return existing
        previous = self._by_intent.get(decision.intent_id)
        if previous is not None and not certificate_expired(previous, issued_at):
            return previous

        authorization = ExecutionAuthorization(
            authorization_id=new_authorization_id(issued_at),
            decision_id=decision.decision_id,
            intent_id=decision.intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=decision.correlation_id,
            approved=True,
            approved_quantity=decision.approved_quantity,
            symbol=getattr(decision, "symbol", "") or "",
            side=getattr(decision, "side", "") or "",
            execution_policy=getattr(decision, "execution_policy", None),
            granted_at=issued_at,
            reason=decision.reason,
        )
        certificate = ExecutionAuthorizationCertificate(
            certificate_id=new_certificate_id(issued_at),
            authorization_id=authorization.authorization_id,
            decision_id=decision.decision_id,
            intent_id=decision.intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=decision.correlation_id,
            approved=True,
            approved_quantity=decision.approved_quantity,
            issued_at=issued_at,
            expires_at=expires_at,
            symbol=authorization.symbol,
            side=authorization.side,
            execution_policy=authorization.execution_policy,
            reason=authorization.reason,
        )
        self._by_decision[decision.decision_id] = certificate
        self._by_intent[decision.intent_id] = certificate
        return certificate


class CertificateVerifier:
    """Unified certificate verification gate for the order request engine."""

    def verify(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        intent_id: str,
        correlation_id: str,
        now: float,
    ) -> None:
        """Verify a certificate; raise ValueError on any failure.

        Checks, in order: approved, not expired, intent binding, correlation
        binding, approved quantity and identity completeness.
        """
        validate_certificate(certificate, now)
        verify_binding(certificate, intent_id, correlation_id)
        if certificate.approved_quantity <= 0:
            raise ValueError("approved quantity must be positive")
        for attribute in (
            "certificate_id",
            "authorization_id",
            "decision_id",
            "intent_id",
            "strategy_id",
            "session_id",
            "signal_id",
            "correlation_id",
        ):
            if not getattr(certificate, attribute):
                raise ValueError(f"certificate identity is incomplete: {attribute}")
