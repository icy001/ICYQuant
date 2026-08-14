"""Order request domain contracts.

Defines the stable protocol that the order request factory (and, later, the
order request service / OMS adapter / execution adapter) implement.  Anything
that consumes an authorization must go through this boundary - an order request
is never built from a raw strategy intent.
"""

from __future__ import annotations

from typing import Optional, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.order.request.model import OrderRequest
    from services.risk.authorization.integration import AuthorizedExecutionContext


@runtime_checkable
class OrderRequestFactoryProtocol(Protocol):
    """Contract for factories that build order requests.

    ``create`` accepts only the authorized execution context plus the order
    execution parameters (order type / time in force / limit price).  The
    symbol, side and quantity are taken from the context - never passed in.
    """

    def create(
        self,
        context: "AuthorizedExecutionContext",
        *,
        order_type: str,
        time_in_force: str,
        limit_price: Optional[float],
        created_at: float,
    ) -> "OrderRequest":
        ...
