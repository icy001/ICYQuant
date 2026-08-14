"""Tests for the order validator (Commit 33 Part 1.2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from services.order.domain.order_type import OrderType
from services.order.engine.validator import (
    OrderValidationError,
    OrderValidator,
)
from services.order.request.state import OrderRequestState


def test_validate_handoff_request_passes(validator: OrderValidator, make_request):
    validator.validate_request(
        make_request(state=OrderRequestState.HANDOFF)
    )


@pytest.mark.parametrize(
    "state",
    [
        OrderRequestState.CREATED,
        OrderRequestState.VALIDATED,
        OrderRequestState.NORMALIZED,
        OrderRequestState.SUBMITTED,
        OrderRequestState.ACCEPTED,
    ],
)
def test_validate_request_rejects_pre_handoff_states(
    validator: OrderValidator, make_request, state
):
    with pytest.raises(OrderValidationError):
        validator.validate_request(make_request(state=state))


def test_validate_request_rejects_market_with_price(
    validator: OrderValidator, make_request
):
    with pytest.raises(OrderValidationError):
        validator.validate_request(
            make_request(order_type="MARKET", limit_price=180.0)
        )


def test_validate_request_rejects_limit_without_price(
    validator: OrderValidator, make_request
):
    with pytest.raises(OrderValidationError):
        validator.validate_request(
            make_request(order_type="LIMIT", limit_price=None)
        )


def test_validate_request_rejects_non_positive_quantity(
    validator: OrderValidator, make_request
):
    with pytest.raises(OrderValidationError):
        validator.validate_request(make_request(quantity=0.0))


def test_validate_request_rejects_missing_lineage(
    validator: OrderValidator, make_request
):
    with pytest.raises(OrderValidationError):
        validator.validate_request(make_request(intent_id=""))


def test_validate_valid_order_passes(validator: OrderValidator, make_order):
    validator.validate(make_order())


def test_validate_market_with_price_rejected(
    validator: OrderValidator, make_order
):
    with pytest.raises(OrderValidationError):
        validator.validate(
            make_order(
                order_type=OrderType.MARKET,
                limit_price=Decimal("180.00"),
            )
        )


def test_validate_limit_without_price_rejected(
    validator: OrderValidator, make_order
):
    with pytest.raises(OrderValidationError):
        validator.validate(
            make_order(order_type=OrderType.LIMIT, limit_price=None)
        )


def test_validate_negative_quantity_rejected(
    validator: OrderValidator, make_order
):
    with pytest.raises(OrderValidationError):
        validator.validate(make_order(quantity=Decimal("-1")))


def test_validate_missing_lineage_rejected(
    validator: OrderValidator, make_order
):
    with pytest.raises(OrderValidationError):
        validator.validate(make_order(authorization_id=""))


def test_validate_does_not_judge_risk(validator: OrderValidator, make_order):
    # A perfectly valid order - risk approval is a separate concern (Spec #13).
    validator.validate(make_order())
