"""
Order application service.
"""

from __future__ import annotations

from uuid import UUID

from .events import (
    OrderCancelled,
    OrderCreated,
    OrderTransition,
)
from .idempotency import IdempotencyRegistry
from .mapper import OrderMapper
from .model import Order
from .publisher import (
    EventPublisher,
)
from .repository import OrderRepository
from .state_machine import (
    OrderStateMachine,
)
from .validator import OrderValidator


class OrderService:
    def __init__(
        self,
        repository: OrderRepository,
        publisher=None,
        registry=None,
    ):
        self.repository = repository
        self.publisher = publisher or EventPublisher()
        self.registry = registry or IdempotencyRegistry()

    async def create(
        self,
        order: Order,
        client_order_id: str | None = None,
    ) -> Order:
        if client_order_id and self.registry.exists(client_order_id):
            existing_order_id = self.registry.get(client_order_id)
            return await self.get(existing_order_id)

        OrderValidator.validate(order)

        model = OrderMapper.to_model(order)

        await self.repository.create(model)

        await self.publisher.publish(OrderCreated(order_id=model.id))

        if client_order_id:
            self.registry.register(client_order_id, model.id)

        return OrderMapper.to_domain(model)

    async def get(
        self,
        order_id: UUID,
    ) -> Order | None:
        model = await self.repository.get(order_id)

        if model is None:
            return None

        return OrderMapper.to_domain(model)

    async def cancel(
        self,
        order_id: UUID,
    ) -> Order | None:
        model = await self.repository.get(order_id)

        if model is None:
            return None

        new_status = OrderStateMachine.apply(
            model.status,
            OrderTransition.CANCEL,
        )

        await self.repository.update_status(
            model,
            new_status,
        )

        await self.publisher.publish(OrderCancelled(order_id=model.id))

        return OrderMapper.to_domain(model)

    async def list_by_symbol(
        self,
        symbol: str,
    ) -> list[Order]:
        models = await self.repository.find_by_symbol(symbol)

        return [OrderMapper.to_domain(m) for m in models]