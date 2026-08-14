from datetime import datetime

import pytest

from services.execution.domain.fill import (
    ExecutionFill,
)


def build_fill(
    execution_id="fill-001",
    quantity=100,
    price=101,
):
    return ExecutionFill(
        execution_id=execution_id,
        execution_request_id="exec-001",
        order_id="order-001",
        quantity=quantity,
        price=price,
        timestamp=datetime.now(),
    )


def test_fill_validation():

    fill = build_fill()

    fill.validate()

    assert fill.execution_id == "fill-001"
    assert fill.quantity == 100
    assert fill.price == 101


def test_invalid_quantity():

    fill = build_fill(
        quantity=0
    )

    with pytest.raises(ValueError):
        fill.validate()


def test_invalid_price():

    fill = build_fill(
        price=0
    )

    with pytest.raises(ValueError):
        fill.validate()
