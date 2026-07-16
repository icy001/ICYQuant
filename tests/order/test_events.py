import pytest

from uuid import uuid4

from services.order import (
    EventPublisher,
    OrderCreated,
)


@pytest.mark.asyncio
async def test_publish():

    called = False

    async def handler(event):

        nonlocal called

        called = True

        assert isinstance(
            event,
            OrderCreated,
        )

    publisher = EventPublisher()

    publisher.subscribe(
        handler
    )

    await publisher.publish(

        OrderCreated(

            order_id=uuid4(),

        )

    )

    assert called