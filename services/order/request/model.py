"""Order request domain model.

An :class:`OrderRequest` is the system's request to create an order - it is
NOT an order.  The OMS has not accepted it yet and it has not reached any
broker or exchange.

The request is generated strictly from an
:class:`~services.risk.authorization.integration.AuthorizedExecutionContext`:
the quantity, symbol and side always come from the risk-approved scope, and the
full authorization lineage is preserved for OMS / execution / ledger /
reconciliation / audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: Order types accepted by the order request domain in this phase.
ORDER_TYPES = frozenset({"MARKET", "LIMIT"})

#: Sides accepted by the order request domain (case-insensitive).
SIDES = frozenset({"BUY", "SELL"})

#: Time-in-force values accepted by the order request domain.
TIME_IN_FORCE_VALUES = frozenset({"DAY", "GTC", "IOC", "FOK"})


@dataclass(frozen=True)
class OrderRequest:
    """Immutable request to create one order.

    ``quantity`` is fixed to the authorization's ``approved_quantity`` ceiling;
    ``limit_price`` must be present for LIMIT and absent for MARKET.
    """

    order_request_id: str

    intent_id: str
    authorization_id: str
    certificate_id: str
    decision_id: str

    strategy_id: str
    session_id: str
    signal_id: str

    correlation_id: str

    symbol: str
    side: str
    quantity: float

    order_type: str
    time_in_force: str

    limit_price: Optional[float]

    created_at: float

    idempotency_key: str

    def as_dict(self) -> dict:
        """Plain mapping used by persistence / adapters."""
        return {
            "order_request_id": self.order_request_id,
            "intent_id": self.intent_id,
            "authorization_id": self.authorization_id,
            "certificate_id": self.certificate_id,
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "limit_price": self.limit_price,
            "created_at": self.created_at,
            "idempotency_key": self.idempotency_key,
        }
