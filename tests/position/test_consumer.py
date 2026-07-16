import pytest

from services.position import PositionConsumer


class FakeService:
    def __init__(self):
        self.trade_id = None

    async def apply_trade_by_id(
        self,
        trade_id,
    ):
        self.trade_id = trade_id


class Event:
    trade_id = "trade-001"


@pytest.mark.asyncio
async def test_consumer():
    service = FakeService()

    consumer = PositionConsumer(
        service
    )

    await consumer.handle(
        Event()
    )

    assert service.trade_id == "trade-001"