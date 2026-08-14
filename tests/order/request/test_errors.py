"""Tests for the order request validation error model."""

import pytest

from services.order.request.errors import (
    OrderRequestErrorCode,
    OrderRequestValidationError,
)


def test_error_codes_have_stable_values():
    assert OrderRequestErrorCode.INVALID_REQUEST.value == "INVALID_REQUEST"
    assert OrderRequestErrorCode.MISSING_LINEAGE.value == "MISSING_LINEAGE"
    assert OrderRequestErrorCode.INVALID_SYMBOL.value == "INVALID_SYMBOL"
    assert OrderRequestErrorCode.INVALID_SIDE.value == "INVALID_SIDE"
    assert OrderRequestErrorCode.INVALID_QUANTITY.value == "INVALID_QUANTITY"
    assert (
        OrderRequestErrorCode.QUANTITY_EXCEEDS_AUTHORIZATION.value
        == "QUANTITY_EXCEEDS_AUTHORIZATION"
    )
    assert OrderRequestErrorCode.INVALID_ORDER_TYPE.value == "INVALID_ORDER_TYPE"
    assert OrderRequestErrorCode.INVALID_PRICE.value == "INVALID_PRICE"
    assert (
        OrderRequestErrorCode.INVALID_TIME_IN_FORCE.value
        == "INVALID_TIME_IN_FORCE"
    )
    assert (
        OrderRequestErrorCode.MISSING_IDEMPOTENCY_KEY.value
        == "MISSING_IDEMPOTENCY_KEY"
    )
    assert (
        OrderRequestErrorCode.MISSING_CORRELATION_ID.value
        == "MISSING_CORRELATION_ID"
    )


def test_validation_error_is_a_value_error():
    error = OrderRequestValidationError(("INVALID_QUANTITY",))
    assert isinstance(error, ValueError)
    assert error.errors == ("INVALID_QUANTITY",)


def test_validation_error_message_joins_errors():
    error = OrderRequestValidationError(("INVALID_QUANTITY", "INVALID_PRICE"))
    assert "INVALID_QUANTITY" in str(error)
    assert "INVALID_PRICE" in str(error)


def test_validation_error_empty_errors():
    error = OrderRequestValidationError(())
    assert error.errors == ()
    assert str(error) == "invalid order request"


def test_validation_error_can_be_raised_as_value_error():
    with pytest.raises(ValueError):
        raise OrderRequestValidationError(("INVALID_SYMBOL",))
