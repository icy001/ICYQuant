import pytest

from services.ledger import (
    AccountingService,
)


class FakeRepository:
    def __init__(self):
        self.saved = False

    async def save(
        self,
        journal,
    ):
        self.saved = True


class FakeTradeRepository:
    pass


class Trade:
    quantity = 100
    price = 10


@pytest.mark.asyncio
async def test_post_trade():
    repository = FakeRepository()
    trade_repository = FakeTradeRepository()

    service = AccountingService(
        repository,
        trade_repository,
    )

    await service.post_trade(
        Trade()
    )

    assert repository.saved