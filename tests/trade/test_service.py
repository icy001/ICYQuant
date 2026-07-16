from decimal import Decimal
from uuid import uuid4

import pytest

from services.trade import (
    TradeService,
)


class FakeRepository:
    def __init__(self):
        self.saved = None

    async def find_by_execution_id(
        self,
        execution_id,
    ):
        return None

    async def create(
        self,
        model,
    ):
        self.saved = model
        return model


@pytest.mark.asyncio
async def test_trade_service_create():
    repository = FakeRepository()

    service = TradeService(
        repository
    )

    class Report:
        execution_id = "EX-001"
        filled_quantity = Decimal("10")
        average_price = Decimal("100")

    class Order:
        order_id = uuid4()
        symbol = "AAPL"

    trade = await service.create_from_execution(
        Report(),
        Order(),
    )

    assert trade.symbol == "AAPL"