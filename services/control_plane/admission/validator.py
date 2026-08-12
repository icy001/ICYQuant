"""
OrderAdmissionValidator — validates an OrderAdmissionRequest before any risk
or control evaluation runs (spec section 6).

Validation failures are *not* exceptions at the service boundary: the service
converts a ``ValueError`` into a REJECTED / INVALID_REQUEST decision so the
caller always receives a first-class AdmissionDecision.
"""

from __future__ import annotations

from .request import OrderAdmissionRequest


class OrderAdmissionValidator:

    def validate(
        self,
        request: OrderAdmissionRequest,
    ) -> None:

        if not request.symbol:
            raise ValueError(
                "symbol is required"
            )

        if not request.side:
            raise ValueError(
                "side is required"
            )

        if not request.order_type:
            raise ValueError(
                "order_type is required"
            )

        if request.quantity <= 0:
            raise ValueError(
                "quantity must be positive"
            )
