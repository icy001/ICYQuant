from decimal import Decimal

import pytest


class FakeRepository:
    def __init__(self):
        self.position = None

    async def find(
        self,
        account_id,
        symbol,
    ):
        return None

    async def save(
        self,
        position,
    ):
        self.position = position


class Trade:
    account_id = "ACC-001"
    symbol = "AAPL"
    quantity = Decimal("100")
    price = Decimal("200")


@pytest.mark.asyncio
async def test_apply_trade():
    from services.position import PositionService

    repository = FakeRepository()

    service = PositionService(
        repository
    )

    position = await service.apply_trade(
        Trade()
    )

    assert position.quantity == Decimal("100")