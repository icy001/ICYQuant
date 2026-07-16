"""
Order integration fixtures.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from services.order import (
    EventPublisher,
    Order,
    OrderRepository,
    OrderService,
    OrderSide,
)


class InMemoryOrderRepository(OrderRepository):
    """
    Lightweight in-memory repository used
    for integration testing.
    """

    def __init__(self):

        self.storage = {}

    async def create(self, model):

        self.storage[model.id] = model

        return model

    async def get(self, order_id):

        return self.storage.get(order_id)

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

        return [

            order

            for order in self.storage.values()

            if order.symbol == symbol

        ]

    async def update_with_version(
        self,
        model,
    ):
        pass


@pytest.fixture
def repository():

    return InMemoryOrderRepository()


@pytest.fixture
def publisher():

    return EventPublisher()


@pytest.fixture
def order_service(
    repository,
    publisher,
):

    return OrderService(
        repository,
        publisher,
    )


@pytest.fixture
def sample_order():

    return Order(

        symbol="AAPL",

        side=OrderSide.BUY,

        quantity=Decimal("100"),

    )