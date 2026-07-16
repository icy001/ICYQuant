from decimal import Decimal
from uuid import uuid4

import pytest

from services.order import (
    ExecutionReport,
    ExecutionReportHandler,
    OrderTransition,
)


@pytest.mark.asyncio
async def test_execution_report_updates_order(
    order_service,
    repository,
    sample_order,
):
    created = await order_service.create(sample_order)

    handler = ExecutionReportHandler(repository)

    accept_report = ExecutionReport(
        order_id=created.order_id,
        transition=OrderTransition.ACCEPT,
    )

    await handler.process(accept_report)

    fill_report = ExecutionReport(
        order_id=created.order_id,
        transition=OrderTransition.FILL,
        filled_quantity=Decimal("100"),
        average_price=Decimal("185.50"),
    )

    updated = await handler.process(fill_report)

    assert updated.filled_quantity == Decimal("100")


@pytest.mark.asyncio
async def test_execution_report_partial_fill(
    order_service,
    repository,
    sample_order,
):
    created = await order_service.create(sample_order)

    handler = ExecutionReportHandler(repository)

    accept_report = ExecutionReport(
        order_id=created.order_id,
        transition=OrderTransition.ACCEPT,
    )

    await handler.process(accept_report)

    report = ExecutionReport(
        order_id=created.order_id,
        transition=OrderTransition.PARTIAL_FILL,
        filled_quantity=Decimal("50"),
        average_price=Decimal("180.00"),
    )

    updated = await handler.process(report)

    assert updated.filled_quantity == Decimal("50")
    assert updated.status.name == "PARTIALLY_FILLED"


@pytest.mark.asyncio
async def test_order_not_found(
    repository,
):
    handler = ExecutionReportHandler(repository)

    report = ExecutionReport(
        order_id=uuid4(),
        transition=OrderTransition.FILL,
    )

    with pytest.raises(LookupError, match="order not found"):
        await handler.process(report)