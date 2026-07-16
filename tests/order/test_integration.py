"""
Order lifecycle integration tests.
"""

from __future__ import annotations

import pytest

from services.order import (

    OrderStatus,

)


@pytest.mark.asyncio

async def test_create_order(

    order_service,

    sample_order,

):

    created = await order_service.create(

        sample_order

    )

    assert created.symbol == "AAPL"

    assert created.status == OrderStatus.NEW


@pytest.mark.asyncio

async def test_cancel_order(

    order_service,

    sample_order,

):

    created = await order_service.create(

        sample_order

    )

    cancelled = await order_service.cancel(

        created.order_id

    )

    assert (

        cancelled.status

        ==

        OrderStatus.CANCELLED

    )


@pytest.mark.asyncio

async def test_find_by_symbol(

    order_service,

    sample_order,

):

    await order_service.create(

        sample_order

    )

    orders = await order_service.list_by_symbol(

        "AAPL"

    )

    assert len(orders) == 1

    assert orders[0].symbol == "AAPL"