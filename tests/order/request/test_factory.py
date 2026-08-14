"""Tests for the OrderRequestFactory (Commit 32 Part 1.1)."""

import pytest

from services.order.request.factory import (
    OrderRequestFactory,
    authorization_idempotency_key,
    new_order_request_id,
)
from services.risk.authorization.integration import AuthorizedExecutionContext


def valid_context(**overrides) -> AuthorizedExecutionContext:
    defaults = dict(
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
        correlation_id="CORR-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
    )
    defaults.update(overrides)
    return AuthorizedExecutionContext(**defaults)


@pytest.fixture
def factory() -> OrderRequestFactory:
    return OrderRequestFactory()


def test_factory_creates_order_request(factory):
    request = factory.create(
        valid_context(),
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=180.0,
        created_at=1000,
    )
    assert request.symbol == "NVDA"
    assert request.side == "BUY"
    assert request.quantity == 100
    assert request.order_type == "LIMIT"
    assert request.time_in_force == "DAY"
    assert request.limit_price == 180.0


def test_quantity_is_taken_from_authorization(factory):
    context = valid_context(approved_quantity=300)
    request = factory.create(
        context,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    assert request.quantity == 300


def test_market_order(factory):
    request = factory.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    assert request.order_type == "MARKET"
    assert request.limit_price is None


def test_limit_order(factory):
    request = factory.create(
        valid_context(),
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=180.0,
        created_at=1000,
    )
    assert request.order_type == "LIMIT"
    assert request.limit_price == 180.0


def test_limit_requires_price(factory):
    with pytest.raises(ValueError, match="limit_price"):
        factory.create(
            valid_context(),
            order_type="LIMIT",
            time_in_force="DAY",
            limit_price=None,
            created_at=1000,
        )


def test_market_cannot_have_limit_price(factory):
    with pytest.raises(ValueError, match="limit_price"):
        factory.create(
            valid_context(),
            order_type="MARKET",
            time_in_force="DAY",
            limit_price=180.0,
            created_at=1000,
        )


def test_order_request_preserves_authorization_lineage(factory):
    context = valid_context()
    request = factory.create(
        context,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    assert request.intent_id == context.intent_id
    assert request.authorization_id == context.authorization_id
    assert request.certificate_id == context.certificate_id
    assert request.decision_id == context.decision_id
    assert request.correlation_id == context.correlation_id
    assert request.strategy_id == context.strategy_id
    assert request.session_id == context.session_id
    assert request.signal_id == context.signal_id


def test_idempotency_key_derived_from_identity(factory):
    request = factory.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    assert request.idempotency_key == "STRAT-001:SESSION-001:INT-001"


def test_order_request_id_is_generated(factory):
    request = factory.create(
        valid_context(),
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000,
    )
    assert request.order_request_id.startswith("OR-")


def test_unsupported_order_type_rejected(factory):
    with pytest.raises(ValueError, match="order_type"):
        factory.create(
            valid_context(),
            order_type="STOP",
            time_in_force="DAY",
            limit_price=None,
            created_at=1000,
        )


def test_unsupported_time_in_force_rejected(factory):
    with pytest.raises(ValueError, match="time_in_force"):
        factory.create(
            valid_context(),
            order_type="MARKET",
            time_in_force="FOREVER",
            limit_price=None,
            created_at=1000,
        )


def test_incomplete_context_rejected(factory):
    with pytest.raises(ValueError, match="incomplete"):
        factory.create(
            valid_context(intent_id=""),
            order_type="MARKET",
            time_in_force="DAY",
            limit_price=None,
            created_at=1000,
        )


def test_non_positive_approved_quantity_rejected(factory):
    with pytest.raises(ValueError, match="quantity"):
        factory.create(
            valid_context(approved_quantity=0),
            order_type="MARKET",
            time_in_force="DAY",
            limit_price=None,
            created_at=1000,
        )


def test_authorization_idempotency_key_shape():
    key = authorization_idempotency_key("STRAT-001", "SESSION-001", "INT-001")
    assert key == "STRAT-001:SESSION-001:INT-001"


def test_new_order_request_id_shape():
    request_id = new_order_request_id(1000)
    assert request_id.startswith("OR-")
    assert len(request_id) > 4
