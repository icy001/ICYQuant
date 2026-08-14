"""Order request factory.

The only way an authorization becomes an order request.  The factory never
re-runs risk evaluation and never accepts quantity / symbol / side from the
caller: everything trade-relevant comes from the
:class:`~services.risk.authorization.integration.AuthorizedExecutionContext`
produced by Commit 31.
"""

from __future__ import annotations

import itertools
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from services.order.request.model import ORDER_TYPES, TIME_IN_FORCE_VALUES, OrderRequest

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.integration import AuthorizedExecutionContext


_order_request_counter = itertools.count(1)


def new_order_request_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic order request id.

    Example: ``OR-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_order_request_counter)
    return f"OR-{date_part}-{sequence:06d}"


def authorization_idempotency_key(
    strategy_id: str,
    session_id: str,
    intent_id: str,
) -> str:
    """The canonical idempotency key for an authorization.

    Example: ``STRAT-001:SESSION-001:INT-001``.
    """
    return f"{strategy_id}:{session_id}:{intent_id}"


class OrderRequestFactory:
    """Builds immutable order requests from authorized execution contexts.

    Domain invariants enforced here:

    * all identity ids are non-empty
    * ``quantity`` is the context's ``approved_quantity`` (> 0)
    * ``order_type`` in {MARKET, LIMIT}
    * ``time_in_force`` in {DAY, GTC, IOC, FOK}
    * LIMIT requires ``limit_price``; MARKET forbids it
    """

    def create(
        self,
        context: "AuthorizedExecutionContext",
        *,
        order_type: str,
        time_in_force: str,
        limit_price: Optional[float],
        created_at: float,
    ) -> OrderRequest:
        """Create one order request from an authorized execution context."""
        if context is None:
            raise ValueError("authorized execution context is required")
        self._validate_context(context)
        self._validate_order_parameters(order_type, time_in_force, limit_price)

        order_type = order_type.upper()
        time_in_force = time_in_force.upper()

        if order_type == "LIMIT" and limit_price is None:
            raise ValueError("LIMIT order requires limit_price")
        if order_type == "MARKET" and limit_price is not None:
            raise ValueError("MARKET order cannot have limit_price")

        return OrderRequest(
            order_request_id=new_order_request_id(created_at),
            intent_id=context.intent_id,
            authorization_id=context.authorization_id,
            certificate_id=context.certificate_id,
            decision_id=context.decision_id,
            strategy_id=context.strategy_id,
            session_id=context.session_id,
            signal_id=context.signal_id,
            correlation_id=context.correlation_id,
            symbol=context.symbol,
            side=context.side,
            quantity=context.approved_quantity,
            order_type=order_type,
            time_in_force=time_in_force,
            limit_price=limit_price,
            created_at=created_at,
            idempotency_key=authorization_idempotency_key(
                context.strategy_id,
                context.session_id,
                context.intent_id,
            ),
        )

    @staticmethod
    def _validate_context(context: "AuthorizedExecutionContext") -> None:
        required = (
            ("intent_id", context.intent_id),
            ("authorization_id", context.authorization_id),
            ("certificate_id", context.certificate_id),
            ("decision_id", context.decision_id),
            ("strategy_id", context.strategy_id),
            ("session_id", context.session_id),
            ("signal_id", context.signal_id),
            ("correlation_id", context.correlation_id),
            ("symbol", context.symbol),
            ("side", context.side),
        )
        for attribute, value in required:
            if not value:
                raise ValueError(f"authorized context is incomplete: {attribute}")
        if context.approved_quantity <= 0:
            raise ValueError("approved quantity must be positive")

    @staticmethod
    def _validate_order_parameters(
        order_type: str,
        time_in_force: str,
        limit_price: Optional[float],
    ) -> None:
        if not order_type:
            raise ValueError("order_type is required")
        if order_type.upper() not in ORDER_TYPES:
            raise ValueError(
                f"unsupported order_type: {order_type}; supported: "
                + ", ".join(sorted(ORDER_TYPES))
            )
        if time_in_force.upper() not in TIME_IN_FORCE_VALUES:
            raise ValueError(
                f"unsupported time_in_force: {time_in_force}; supported: "
                + ", ".join(sorted(TIME_IN_FORCE_VALUES))
            )
        if limit_price is not None and limit_price <= 0:
            raise ValueError("limit_price must be positive")
