"""Order request normalization.

After a request passes validation it is canonicalized into a
:class:`NormalizedOrderRequest`: side / order type / time-in-force are folded to
their canonical uppercase form and the symbol is trimmed.

Normalization is canonicalization, not repair: it removes format differences
but never guesses at semantics.  A symbol like ``"NV DA"`` is rejected instead
of being "fixed" to ``"NVDA"``, and a BUY is never turned into a SELL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from services.order.request.errors import OrderRequestValidationError
from services.order.request.model import OrderRequest
from services.order.request.validation import OrderRequestValidator, is_valid_symbol

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from services.risk.authorization.integration import AuthorizedExecutionContext


@dataclass(frozen=True)
class NormalizedOrderRequest:
    """Canonical, validated form of an order request ready for the OMS.

    Deliberately mirrors :class:`OrderRequest`; the difference is that this
    object has passed domain validation and canonical normalization.
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


class OrderRequestNormalizer:
    """Validates then canonicalizes an order request.

    Pipeline::

        OrderRequest
            -> validate (raw)
            -> canonicalize (side / order_type / time_in_force / symbol)
            -> validate (normalized)
            -> NormalizedOrderRequest

    The normalizer never bypasses the validator and never rewrites illegal data
    into something that merely *looks* legal.
    """

    def __init__(self, *, validator: Optional[OrderRequestValidator] = None) -> None:
        self.validator = validator if validator is not None else OrderRequestValidator()

    def normalize(
        self,
        request: OrderRequest,
        *,
        approved_quantity: Optional[float] = None,
    ) -> NormalizedOrderRequest:
        """Validate and canonicalize the request.

        Raises :class:`OrderRequestValidationError` (a ``ValueError``) when the
        raw or normalized request is invalid.
        """
        raw = self.validator.validate(request, approved_quantity=approved_quantity)
        if not raw.valid:
            raise OrderRequestValidationError(raw.errors)

        canonical = self._canonicalize(request)
        post = self.validator.validate(canonical, approved_quantity=approved_quantity)
        if not post.valid:
            raise OrderRequestValidationError(post.errors)

        return NormalizedOrderRequest(
            order_request_id=canonical.order_request_id,
            intent_id=canonical.intent_id,
            authorization_id=canonical.authorization_id,
            certificate_id=canonical.certificate_id,
            decision_id=canonical.decision_id,
            strategy_id=canonical.strategy_id,
            session_id=canonical.session_id,
            signal_id=canonical.signal_id,
            correlation_id=canonical.correlation_id,
            symbol=canonical.symbol,
            side=canonical.side,
            quantity=canonical.quantity,
            order_type=canonical.order_type,
            time_in_force=canonical.time_in_force,
            limit_price=canonical.limit_price,
            created_at=canonical.created_at,
            idempotency_key=canonical.idempotency_key,
        )

    @staticmethod
    def _canonicalize(request: OrderRequest) -> OrderRequest:
        symbol = request.symbol.strip()
        if not is_valid_symbol(symbol):
            raise OrderRequestValidationError(("INVALID_SYMBOL",))
        return OrderRequest(
            order_request_id=request.order_request_id,
            intent_id=request.intent_id,
            authorization_id=request.authorization_id,
            certificate_id=request.certificate_id,
            decision_id=request.decision_id,
            strategy_id=request.strategy_id,
            session_id=request.session_id,
            signal_id=request.signal_id,
            correlation_id=request.correlation_id,
            symbol=symbol,
            side=request.side.strip().upper(),
            quantity=request.quantity,
            order_type=request.order_type.strip().upper(),
            time_in_force=request.time_in_force.strip().upper(),
            limit_price=request.limit_price,
            created_at=request.created_at,
            idempotency_key=request.idempotency_key,
        )
