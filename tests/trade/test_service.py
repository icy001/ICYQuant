from decimal import Decimal
from uuid import uuid4

import pytest

from services.trade import TradeService


class FakeRepository:
    def __init__(self):
        self.saved = None

    async def find_by_execution_id(
        self,
        execution_id,
    ):
        return None

    async def save(
        self,
        trade,
    ):
        self.saved = trade

        class FakeModel:
            id = trade.trade_id
            order_id = str(trade.order_id)
            account_id = trade.account_id
            symbol = trade.symbol
            quantity = trade.quantity
            price = trade.price
            execution_id = trade.execution_id
            commission = trade.commission
            created_at = trade.executed_at

        return FakeModel()


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
        account_id = "ACC-001"
        symbol = "AAPL"

    trade = await service.create_from_execution(
        Report(),
        Order(),
    )

    assert trade.symbol == "AAPL"
    assert trade.account_id == "ACC-001"