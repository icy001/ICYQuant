"""Risk authorization contracts - the requests and authorizations that cross
domain boundaries inside the risk engine.

The full authorization pipeline is::

    Execution Intent
        -> Risk Authorization Request
        -> Risk Evaluation
        -> Risk Decision
        -> Execution Authorization
        -> Authorization Certificate

:class:`RiskAuthorizationRequest` is what the execution domain hands to risk.
:class:`ExecutionAuthorization` is the risk engine's own statement that a
decision grants an authorization - it carries the generated
``authorization_id`` that later identifies the certificate.  The chain stays
strictly 1:1: one decision -> one authorization -> one certificate.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from services.risk.authorization.decision import RiskDecision

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.strategy.execution.snapshot import IntentSnapshot


@dataclass(frozen=True)
class RiskAuthorizationRequest:
    """Frozen request handed from the execution domain to the risk engine.

    Built from an :class:`IntentSnapshot` so risk decides on exactly what the
    strategy expressed at handoff time.
    """

    request_id: str
    intent_id: str
    strategy_id: str
    session_id: str
    signal_id: str
    correlation_id: str

    symbol: str
    side: str
    target_quantity: float

    execution_policy: str
    urgency: str

    submitted_at: float

    @classmethod
    def from_snapshot(
        cls,
        snapshot: "IntentSnapshot",
        *,
        submitted_at: float,
        request_id: Optional[str] = None,
    ) -> "RiskAuthorizationRequest":
        if not snapshot.correlation_id:
            raise ValueError("correlation_id is required for an authorization request")
        return cls(
            request_id=request_id or new_request_id(submitted_at),
            intent_id=snapshot.intent_id,
            strategy_id=snapshot.strategy_id,
            session_id=snapshot.session_id,
            signal_id=snapshot.signal_id,
            correlation_id=snapshot.correlation_id,
            symbol=snapshot.symbol,
            side=snapshot.side,
            target_quantity=snapshot.target_quantity,
            execution_policy=snapshot.execution_policy,
            urgency=snapshot.urgency,
            submitted_at=submitted_at,
        )

    def as_dict(self) -> dict[str, Any]:
        """Audit-ready plain mapping of the request."""
        return {
            "request_id": self.request_id,
            "intent_id": self.intent_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "symbol": self.symbol,
            "side": self.side,
            "target_quantity": self.target_quantity,
            "execution_policy": self.execution_policy,
            "urgency": self.urgency,
            "submitted_at": self.submitted_at,
        }


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Risk engine's grant of one risk decision.

    ``authorization_id`` is generated once per approved decision and the
    certificate issued from it reuses the same id, keeping the whole chain
    1 decision : 1 authorization : 1 certificate.
    """

    authorization_id: str
    decision_id: str
    intent_id: str
    strategy_id: str
    session_id: str
    signal_id: str
    correlation_id: str

    approved: bool
    approved_quantity: Optional[float]

    symbol: str = ""
    side: str = ""
    execution_policy: Optional[str] = None

    granted_at: float = 0.0
    reason: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        """Audit-ready plain mapping of the authorization."""
        return {
            "authorization_id": self.authorization_id,
            "decision_id": self.decision_id,
            "intent_id": self.intent_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "approved": self.approved,
            "approved_quantity": self.approved_quantity,
            "symbol": self.symbol,
            "side": self.side,
            "execution_policy": self.execution_policy,
            "granted_at": self.granted_at,
            "reason": self.reason,
        }


_authorization_counter = itertools.count(1)
_request_counter = itertools.count(1)


def new_authorization_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic authorization id.

    Example: ``AUTH-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_authorization_counter)
    return f"AUTH-{date_part}-{sequence:06d}"


def new_request_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic risk authorization request id.

    Example: ``RAUTH-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_request_counter)
    return f"RAUTH-{date_part}-{sequence:06d}"


def authorization_from_decision(
    decision: RiskDecision,
    *,
    authorization_id: Optional[str] = None,
    granted_at: Optional[float] = None,
) -> ExecutionAuthorization:
    """Turn an approved risk decision into an execution authorization."""
    reference = time.time() if granted_at is None else granted_at
    return ExecutionAuthorization(
        authorization_id=authorization_id or new_authorization_id(reference),
        decision_id=decision.decision_id,
        intent_id=decision.intent_id,
        strategy_id=decision.strategy_id,
        session_id=decision.session_id,
        signal_id=decision.signal_id,
        correlation_id=decision.correlation_id,
        approved=decision.approved,
        approved_quantity=decision.approved_quantity,
        symbol=decision.symbol,
        side=decision.side,
        execution_policy=decision.execution_policy,
        granted_at=reference,
        reason=decision.reason,
    )
