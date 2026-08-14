"""Tests for the OrderRequestNormalizer (Commit 32 Part 1.2)."""

from dataclasses import FrozenInstanceError

import pytest

from services.order.request.errors import OrderRequestValidationError
from services.order.request.model import OrderRequest
from services.order.request.normalization import (
    NormalizedOrderRequest,
    OrderRequestNormalizer,
)


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
def normalizer() -> OrderRequestNormalizer:
    return OrderRequestNormalizer()


def test_request_is_normalized(normalizer):
    request = make_request(
        side="buy",
        order_type="limit",
        time_in_force="day",
        symbol=" NVDA ",
        limit_price=180.0,
    )
    normalized = normalizer.normalize(request)
    assert normalized.side == "BUY"
    assert normalized.order_type == "LIMIT"
    assert normalized.time_in_force == "DAY"
    assert normalized.symbol == "NVDA"


def test_normalizer_does_not_guess_symbol(normalizer):
    request = make_request(symbol="NV DA")
    with pytest.raises(ValueError):
        normalizer.normalize(request)


def test_normalizer_does_not_repair_side(normalizer):
    request = make_request(side="BUY")
    normalized = normalizer.normalize(request)
    assert normalized.side == "BUY"  # BUY never becomes SELL


def test_normalizer_does_not_change_quantity(normalizer):
    request = make_request(quantity=100)
    normalized = normalizer.normalize(request)
    assert normalized.quantity == 100


def test_normalizer_does_not_change_price(normalizer):
    request = make_request(order_type="LIMIT", limit_price=180.0)
    normalized = normalizer.normalize(request)
    assert normalized.limit_price == 180.0


def test_normalization_preserves_lineage(normalizer):
    request = make_request(
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
    )
    normalized = normalizer.normalize(request)
    assert normalized.intent_id == "INT-001"
    assert normalized.authorization_id == "AUTH-001"
    assert normalized.certificate_id == "CERT-001"
    assert normalized.decision_id == "RISK-001"
    assert normalized.correlation_id == "CORR-001"
    assert normalized.strategy_id == "STRAT-001"
    assert normalized.session_id == "SESSION-001"
    assert normalized.signal_id == "SIG-001"


def test_normalization_preserves_idempotency_key(normalizer):
    request = make_request(idempotency_key="STRAT-001:SESSION-001:INT-001")
    normalized = normalizer.normalize(request)
    assert normalized.idempotency_key == "STRAT-001:SESSION-001:INT-001"


def test_normalized_request_is_frozen(normalizer):
    normalized = normalizer.normalize(make_request())
    with pytest.raises(FrozenInstanceError):
        normalized.side = "SELL"


def test_invalid_raw_request_is_rejected_before_normalization(normalizer):
    request = make_request(quantity=0)
    with pytest.raises(OrderRequestValidationError):
        normalizer.normalize(request)


def test_invalid_normalized_request_is_rejected(normalizer):
    request = make_request(order_type="LIMIT", limit_price=None)
    with pytest.raises(OrderRequestValidationError):
        normalizer.normalize(request)


def test_normalized_request_as_dict(normalizer):
    normalized = normalizer.normalize(make_request())
    data = normalized.as_dict()
    assert data["symbol"] == "NVDA"
    assert data["side"] == "BUY"
    assert data["quantity"] == 100.0


def test_normalize_with_approved_quantity_ceiling(normalizer):
    request = make_request(quantity=101)
    with pytest.raises(OrderRequestValidationError):
        normalizer.normalize(request, approved_quantity=100)


def test_normalize_accepts_approved_quantity_within_ceiling(normalizer):
    normalized = normalizer.normalize(make_request(quantity=80), approved_quantity=100)
    assert normalized.quantity == 80


def test_market_order_normalization(normalizer):
    request = make_request(order_type="market", time_in_force="day")
    normalized = normalizer.normalize(request)
    assert normalized.order_type == "MARKET"
    assert normalized.time_in_force == "DAY"
    assert normalized.limit_price is None


def test_symbol_trim_is_safe(normalizer):
    request = make_request(symbol=" NVDA ")
    normalized = normalizer.normalize(request)
    assert normalized.symbol == "NVDA"


def test_normalized_request_type(normalizer):
    normalized = normalizer.normalize(make_request())
    assert isinstance(normalized, NormalizedOrderRequest)
