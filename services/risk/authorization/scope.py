"""Authorization scope - the exact boundary a certificate authorizes.

A certificate is NOT "this strategy may trade freely": it authorizes exactly
one intent (one symbol / side / quantity ceiling) within one strategy session.
:class:`AuthorizationScope` fixes that boundary so the execution eligibility
validator can answer a single question: does this execution request match
what risk approved?
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.certificate import ExecutionAuthorizationCertificate
    from services.risk.authorization.decision import RiskDecision


@dataclass(frozen=True)
class AuthorizationScope:
    """Immutable execution boundary granted by one authorization.

    The scope pins the authorization to a single strategy / session / signal /
    intent and to one symbol / side with an approved quantity ceiling.
    """

    strategy_id: str
    session_id: str
    signal_id: str
    intent_id: str

    symbol: str
    side: str

    approved_quantity: float

    def as_dict(self) -> dict[str, Any]:
        """Audit-ready plain mapping of the scope."""
        return {
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": self.side,
            "approved_quantity": self.approved_quantity,
        }


def scope_from_certificate(
    certificate: "ExecutionAuthorizationCertificate",
) -> AuthorizationScope:
    """Derive the authorization scope fixed by a certificate."""
    return AuthorizationScope(
        strategy_id=certificate.strategy_id,
        session_id=certificate.session_id,
        signal_id=certificate.signal_id,
        intent_id=certificate.intent_id,
        symbol=certificate.symbol,
        side=certificate.side,
        approved_quantity=certificate.approved_quantity,
    )


def scope_from_decision(decision: "RiskDecision") -> AuthorizationScope:
    """Derive the authorization scope expressed by a risk decision."""
    return AuthorizationScope(
        strategy_id=decision.strategy_id,
        session_id=decision.session_id,
        signal_id=decision.signal_id,
        intent_id=decision.intent_id,
        symbol=decision.symbol,
        side=decision.side,
        approved_quantity=decision.approved_quantity or 0.0,
    )
