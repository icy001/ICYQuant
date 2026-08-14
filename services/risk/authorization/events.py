"""Risk authorization lifecycle events.

Events describe *what happened* (facts) rather than the current state of an
authorization.  The full lifecycle is::

    REQUESTED
        -> APPROVED / REJECTED
        -> ISSUED
        -> VERIFIED
        -> CONSUMED
        -> EXPIRED

Each event carries the full lineage (strategy / session / signal / intent /
decision / authorization / certificate / correlation) plus a per-correlation
``sequence`` and ``previous_event_id`` so the timeline can be audited and a
broken chain detected.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.certificate import ExecutionAuthorizationCertificate
    from services.risk.authorization.contract import RiskAuthorizationRequest
    from services.risk.authorization.decision import RiskDecision


class AuthorizationEventType(str, Enum):
    """Machine-readable event types of the authorization lifecycle."""

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ISSUED = "ISSUED"
    VERIFIED = "VERIFIED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class AuthorizationEventMetadata:
    """Schema metadata attached to every authorization event."""

    source: str = "risk.authorization"
    version: str = "1"
    environment: str = "production"


@dataclass(frozen=True)
class AuthorizationEvent:
    """One immutable fact in the authorization timeline.

    ``sequence`` is monotonic per ``correlation_id`` and ``previous_event_id``
    links the event to its predecessor, forming an authorization event lineage.
    """

    event_id: str
    event_type: AuthorizationEventType

    authorization_id: str
    certificate_id: Optional[str]
    decision_id: str
    intent_id: str

    strategy_id: str
    session_id: str
    signal_id: str

    correlation_id: str

    occurred_at: float

    reason: Optional[str] = None

    #: per-correlation monotonic sequence (event timeline ordering)
    sequence: int = 0
    #: id of the previous event in the same correlation chain
    previous_event_id: Optional[str] = None

    #: fixed on APPROVED / ISSUED events
    approved_quantity: Optional[float] = None
    #: fixed on CONSUMED events
    order_request_id: Optional[str] = None


_event_counter = itertools.count(1)


def new_event_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic authorization event id.

    Example: ``EVT-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_event_counter)
    return f"EVT-{date_part}-{sequence:06d}"


class AuthorizationEventFactory:
    """Single place that constructs authorization events.

    The factory keeps a per-correlation sequence counter and links every event
    to its predecessor, so business code never assembles events by hand and the
    event timeline stays consistent.
    """

    def __init__(
        self,
        *,
        metadata: Optional[AuthorizationEventMetadata] = None,
        clock: Optional[float] = None,
    ) -> None:
        self.metadata = metadata or AuthorizationEventMetadata()
        self._clock = clock if clock is not None else time.time()
        self._sequences: dict[str, int] = {}
        self._last_event_ids: dict[str, str] = {}

    def _emit(
        self,
        event_type: AuthorizationEventType,
        *,
        authorization_id: str = "",
        certificate_id: Optional[str] = None,
        decision_id: str = "",
        intent_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        correlation_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
        approved_quantity: Optional[float] = None,
        order_request_id: Optional[str] = None,
    ) -> AuthorizationEvent:
        reference = self._clock if occurred_at is None else occurred_at
        bucket = correlation_id or "__default__"
        sequence = self._sequences.get(bucket, 0) + 1
        previous_event_id = self._last_event_ids.get(bucket)
        self._sequences[bucket] = sequence

        event = AuthorizationEvent(
            event_id=new_event_id(reference),
            event_type=event_type,
            authorization_id=authorization_id,
            certificate_id=certificate_id,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=reference,
            reason=reason,
            sequence=sequence,
            previous_event_id=previous_event_id,
            approved_quantity=approved_quantity,
            order_request_id=order_request_id,
        )
        self._last_event_ids[bucket] = event.event_id
        return event

    # --- primitive builders -------------------------------------------------

    def requested(
        self,
        *,
        intent_id: str,
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        correlation_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.REQUESTED,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
        )

    def approved(
        self,
        *,
        decision_id: str = "",
        intent_id: str = "",
        approved_quantity: Optional[float] = None,
        correlation_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        authorization_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.APPROVED,
            authorization_id=authorization_id,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
            approved_quantity=approved_quantity,
        )

    def rejected(
        self,
        *,
        decision_id: str = "",
        intent_id: str = "",
        correlation_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.REJECTED,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
        )

    def issued(
        self,
        *,
        certificate_id: str = "",
        authorization_id: str = "",
        decision_id: str = "",
        intent_id: str = "",
        approved_quantity: Optional[float] = None,
        correlation_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.ISSUED,
            authorization_id=authorization_id,
            certificate_id=certificate_id,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
            approved_quantity=approved_quantity,
        )

    def verified(
        self,
        *,
        certificate_id: str = "",
        intent_id: str = "",
        correlation_id: str = "",
        authorization_id: str = "",
        decision_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.VERIFIED,
            authorization_id=authorization_id,
            certificate_id=certificate_id,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
        )

    def consumed(
        self,
        *,
        certificate_id: str = "",
        intent_id: str = "",
        correlation_id: str = "",
        order_request_id: str = "",
        authorization_id: str = "",
        decision_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.CONSUMED,
            authorization_id=authorization_id,
            certificate_id=certificate_id,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
            order_request_id=order_request_id,
        )

    def expired(
        self,
        *,
        certificate_id: str = "",
        authorization_id: str = "",
        intent_id: str = "",
        correlation_id: str = "",
        decision_id: str = "",
        strategy_id: str = "",
        session_id: str = "",
        signal_id: str = "",
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self._emit(
            AuthorizationEventType.EXPIRED,
            authorization_id=authorization_id,
            certificate_id=certificate_id,
            decision_id=decision_id,
            intent_id=intent_id,
            strategy_id=strategy_id,
            session_id=session_id,
            signal_id=signal_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            reason=reason,
        )

    # --- object convenience builders ----------------------------------------

    def requested_from_request(
        self,
        request: "RiskAuthorizationRequest",
        *,
        occurred_at: Optional[float] = None,
    ) -> AuthorizationEvent:
        return self.requested(
            intent_id=request.intent_id,
            strategy_id=request.strategy_id,
            session_id=request.session_id,
            signal_id=request.signal_id,
            correlation_id=request.correlation_id,
            occurred_at=occurred_at,
        )

    def approved_from_decision(
        self,
        decision: "RiskDecision",
        *,
        authorization_id: str = "",
        occurred_at: Optional[float] = None,
    ) -> AuthorizationEvent:
        return self.approved(
            decision_id=decision.decision_id,
            intent_id=decision.intent_id,
            approved_quantity=decision.approved_quantity,
            correlation_id=decision.correlation_id,
            strategy_id=decision.strategy_id,
            session_id=decision.session_id,
            signal_id=decision.signal_id,
            authorization_id=authorization_id,
            occurred_at=occurred_at,
            reason=decision.reason,
        )

    def rejected_from_decision(
        self,
        decision: "RiskDecision",
        *,
        occurred_at: Optional[float] = None,
    ) -> AuthorizationEvent:
        return self.rejected(
            decision_id=decision.decision_id,
            intent_id=decision.intent_id,
            correlation_id=decision.correlation_id,
            strategy_id=decision.strategy_id,
            session_id=decision.session_id,
            signal_id=decision.signal_id,
            occurred_at=occurred_at,
            reason=decision.reason,
        )

    def issued_from_certificate(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        occurred_at: Optional[float] = None,
    ) -> AuthorizationEvent:
        return self.issued(
            certificate_id=certificate.certificate_id,
            authorization_id=certificate.authorization_id,
            decision_id=certificate.decision_id,
            intent_id=certificate.intent_id,
            approved_quantity=certificate.approved_quantity,
            correlation_id=certificate.correlation_id,
            strategy_id=certificate.strategy_id,
            session_id=certificate.session_id,
            signal_id=certificate.signal_id,
            occurred_at=occurred_at,
            reason=certificate.reason,
        )

    def verified_from_certificate(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        occurred_at: Optional[float] = None,
    ) -> AuthorizationEvent:
        return self.verified(
            certificate_id=certificate.certificate_id,
            intent_id=certificate.intent_id,
            correlation_id=certificate.correlation_id,
            authorization_id=certificate.authorization_id,
            decision_id=certificate.decision_id,
            strategy_id=certificate.strategy_id,
            session_id=certificate.session_id,
            signal_id=certificate.signal_id,
            occurred_at=occurred_at,
        )

    def consumed_from_certificate(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        order_request_id: str,
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self.consumed(
            certificate_id=certificate.certificate_id,
            intent_id=certificate.intent_id,
            correlation_id=certificate.correlation_id,
            order_request_id=order_request_id,
            authorization_id=certificate.authorization_id,
            decision_id=certificate.decision_id,
            strategy_id=certificate.strategy_id,
            session_id=certificate.session_id,
            signal_id=certificate.signal_id,
            occurred_at=occurred_at,
            reason=reason,
        )

    def expired_from_certificate(
        self,
        certificate: "ExecutionAuthorizationCertificate",
        *,
        occurred_at: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> AuthorizationEvent:
        return self.expired(
            certificate_id=certificate.certificate_id,
            authorization_id=certificate.authorization_id,
            intent_id=certificate.intent_id,
            correlation_id=certificate.correlation_id,
            decision_id=certificate.decision_id,
            strategy_id=certificate.strategy_id,
            session_id=certificate.session_id,
            signal_id=certificate.signal_id,
            occurred_at=occurred_at,
            reason=reason,
        )
