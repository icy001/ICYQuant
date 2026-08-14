"""Tests for the OrderRequestValidator (Commit 32 Part 1.2)."""

import pytest

from services.order.request.errors import OrderRequestErrorCode
from services.order.request.model import OrderRequest
from services.order.request.validation import OrderRequestValidator


def make_request(**overrides) -> OrderRequest:
    defaults = dict(
        order_request_id="OR-20260813-000001",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        quantity=100.0,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000.0,
        idempotency_key="STRAT-001:SESSION-001:INT-001",
    )
    defaults.update(overrides)
    return OrderRequest(**defaults)


@pytest.fixture
def validator() -> OrderRequestValidator:
    return OrderRequestValidator()


def test_valid_request_passes(validator):
    result = validator.validate(make_request())
    assert result.valid is True
    assert result.errors == ()


def test_invalid_quantity_is_rejected(validator):
    result = validator.validate(make_request(quantity=0))
    assert result.valid is False
    assert "INVALID_QUANTITY" in result.errors


def test_negative_quantity_is_rejected(validator):
    result = validator.validate(make_request(quantity=-1))
    assert result.valid is False
    assert "INVALID_QUANTITY" in result.errors


def test_nan_quantity_is_rejected(validator):
    result = validator.validate(make_request(quantity=float("nan")))
    assert result.valid is False
    assert "INVALID_QUANTITY" in result.errors


def test_infinite_quantity_is_rejected(validator):
    result = validator.validate(make_request(quantity=float("inf")))
    assert result.valid is False
    assert "INVALID_QUANTITY" in result.errors


def test_limit_requires_positive_price(validator):
    result = validator.validate(make_request(order_type="LIMIT", limit_price=0))
    assert result.valid is False
    assert "INVALID_PRICE" in result.errors


def test_limit_negative_price_is_rejected(validator):
    result = validator.validate(make_request(order_type="LIMIT", limit_price=-10))
    assert result.valid is False
    assert "INVALID_PRICE" in result.errors


def test_limit_without_price_is_rejected(validator):
    result = validator.validate(make_request(order_type="LIMIT", limit_price=None))
    assert result.valid is False
    assert "INVALID_PRICE" in result.errors


def test_limit_nan_price_is_rejected(validator):
    result = validator.validate(make_request(order_type="LIMIT", limit_price=float("nan")))
    assert result.valid is False
    assert "INVALID_PRICE" in result.errors


def test_market_order_cannot_have_price(validator):
    result = validator.validate(make_request(order_type="MARKET", limit_price=180))
    assert result.valid is False
    assert "INVALID_PRICE" in result.errors


def test_missing_lineage_is_rejected(validator):
    result = validator.validate(make_request(certificate_id=""))
    assert result.valid is False
    assert "MISSING_LINEAGE" in result.errors


def test_missing_correlation_id_is_rejected(validator):
    result = validator.validate(make_request(correlation_id=""))
    assert result.valid is False
    assert "MISSING_CORRELATION_ID" in result.errors


def test_missing_idempotency_key_is_rejected(validator):
    result = validator.validate(make_request(idempotency_key=""))
    assert result.valid is False
    assert "MISSING_IDEMPOTENCY_KEY" in result.errors


def test_invalid_symbol_is_rejected(validator):
    result = validator.validate(make_request(symbol=""))
    assert result.valid is False
    assert "INVALID_SYMBOL" in result.errors


def test_whitespace_symbol_is_rejected(validator):
    result = validator.validate(make_request(symbol="   "))
    assert result.valid is False
    assert "INVALID_SYMBOL" in result.errors


def test_symbol_with_control_character_is_rejected(validator):
    result = validator.validate(make_request(symbol="\nNVDA"))
    assert result.valid is False
    assert "INVALID_SYMBOL" in result.errors


def test_symbol_with_inner_space_is_rejected(validator):
    result = validator.validate(make_request(symbol="NV DA"))
    assert result.valid is False
    assert "INVALID_SYMBOL" in result.errors


def test_invalid_side_is_rejected(validator):
    result = validator.validate(make_request(side="HOLD"))
    assert result.valid is False
    assert "INVALID_SIDE" in result.errors


def test_lowercase_side_is_accepted_by_validator(validator):
    # The validator is read-only: it accepts case variants and lets the
    # normalizer fold them to canonical form.
    result = validator.validate(make_request(side="buy"))
    assert result.valid is True


def test_lowercase_order_type_is_accepted_by_validator(validator):
    result = validator.validate(make_request(order_type="limit", limit_price=180.0))
    assert result.valid is True


def test_invalid_order_type_is_rejected(validator):
    result = validator.validate(make_request(order_type="STOP"))
    assert result.valid is False
    assert "INVALID_ORDER_TYPE" in result.errors


def test_invalid_time_in_force_is_rejected(validator):
    result = validator.validate(make_request(time_in_force="FOREVER"))
    assert result.valid is False
    assert "INVALID_TIME_IN_FORCE" in result.errors


def test_market_gtc_is_rejected(validator):
    # MARKET is compatible with DAY / IOC / FOK, not GTC.
    result = validator.validate(make_request(order_type="MARKET", time_in_force="GTC"))
    assert result.valid is False
    assert "INVALID_TIME_IN_FORCE" in result.errors


def test_market_ioc_is_accepted(validator):
    result = validator.validate(make_request(order_type="MARKET", time_in_force="IOC"))
    assert result.valid is True


def test_limit_gtc_is_accepted(validator):
    result = validator.validate(
        make_request(order_type="LIMIT", time_in_force="GTC", limit_price=180.0)
    )
    assert result.valid is True


def test_quantity_cannot_exceed_authorization(validator):
    request = make_request(quantity=101)
    result = validator.validate(request, approved_quantity=100)
    assert result.valid is False
    assert "QUANTITY_EXCEEDS_AUTHORIZATION" in result.errors


def test_quantity_within_authorization_is_accepted(validator):
    result = validator.validate(make_request(quantity=80), approved_quantity=100)
    assert result.valid is True


def test_quantity_ceiling_from_constructor():
    validator = OrderRequestValidator(approved_quantity=100)
    result = validator.validate(make_request(quantity=101))
    assert result.valid is False
    assert "QUANTITY_EXCEEDS_AUTHORIZATION" in result.errors


def test_all_errors_are_collected_at_once(validator):
    result = validator.validate(
        make_request(
            quantity=0,
            symbol="",
            order_type="STOP",
            idempotency_key="",
        )
    )
    assert result.valid is False
    assert "INVALID_QUANTITY" in result.errors
    assert "INVALID_SYMBOL" in result.errors
    assert "INVALID_ORDER_TYPE" in result.errors
    assert "MISSING_IDEMPOTENCY_KEY" in result.errors


def test_validator_does_not_modify_request(validator):
    request = make_request(side="buy", order_type="limit", symbol=" NVDA ")
    original = request.as_dict()
    validator.validate(request)
    assert request.as_dict() == original


def test_none_request_is_invalid(validator):
    result = validator.validate(None)
    assert result.valid is False
    assert OrderRequestErrorCode.INVALID_REQUEST.value in result.errors
