from __future__ import annotations

from uuid import uuid4

from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionSide,
)


class ExecutionRequestFactory:

    def create(
        self,
        *,
        order_id: str,
        symbol: str,
        side: ExecutionSide,
        order_type: ExecutionOrderType,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        strategy_id: str | None = None,
    ) -> ExecutionRequest:

        request = ExecutionRequest(
            request_id=str(uuid4()),
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            strategy_id=strategy_id,
        )

        request.validate()

        return request
