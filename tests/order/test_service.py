from decimal import Decimal

import pytest

from services.order import (
    Order,
    OrderRepository,
    OrderService,
    OrderSide,
)


class MockRepository(OrderRepository):

    def __init__(self):
        pass

    async def create(self, model):
        self.model_instance = model
        return model

    async def get(self, _):
        return self.model_instance

    async def update_status(
        self,
        model,
        status,
    ):
        model.status = status

    async def find_by_symbol(
        self,
        symbol,
    ):
        return [self.model_instance]


@pytest.mark.asyncio
async def test_create_order():

    repo = MockRepository()

    service = OrderService(repo)

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
    )

    created = await service.create(
        order
    )

    assert created.symbol == "AAPL"


@pytest.mark.asyncio
async def test_cancel_order():

    repo = MockRepository()

    service = OrderService(repo)

    order = Order(
        symbol="MSFT",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
    )

    await service.create(order)

    cancelled = await service.cancel(
        order.order_id
    )

    assert cancelled.status.name == "CANCELLED"