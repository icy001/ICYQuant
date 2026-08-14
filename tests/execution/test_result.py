import pytest

from services.execution.domain.result import (
    ExecutionResult,
)


def test_partial_fill():

    result = ExecutionResult(
        requested_quantity=1000
    )

    result.apply_fill(
        quantity=300,
        price=100,
    )

    assert result.filled_quantity == 300
    assert result.remaining_quantity == 700
    assert not result.fully_filled


def test_multiple_fills():

    result = ExecutionResult(
        requested_quantity=1000
    )

    result.apply_fill(
        quantity=300,
        price=100,
    )

    result.apply_fill(
        quantity=400,
        price=101,
    )

    result.apply_fill(
        quantity=300,
        price=102,
    )

    assert result.filled_quantity == 1000
    assert result.remaining_quantity == 0
    assert result.fully_filled

    assert result.average_fill_price == 101


def test_over_fill_is_rejected():

    result = ExecutionResult(
        requested_quantity=100
    )

    with pytest.raises(ValueError):
        result.apply_fill(
            quantity=101,
            price=100,
        )


def test_non_positive_fill_quantity_is_rejected():

    result = ExecutionResult(
        requested_quantity=100
    )

    with pytest.raises(ValueError):
        result.apply_fill(
            quantity=0,
            price=100,
        )


def test_non_positive_fill_price_is_rejected():

    result = ExecutionResult(
        requested_quantity=100
    )

    with pytest.raises(ValueError):
        result.apply_fill(
            quantity=10,
            price=0,
        )


def test_average_price_moves_with_each_fill():

    result = ExecutionResult(
        requested_quantity=1000
    )

    result.apply_fill(quantity=300, price=100)
    assert result.average_fill_price == 100

    result.apply_fill(quantity=400, price=101)
    assert result.last_fill_price == 101
    assert result.average_fill_price == (
        (300 * 100 + 400 * 101) / 700
    )
