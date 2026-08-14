"""Shared fixtures for order engine tests (Commit 33 Part 1.2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from services.order.domain.order import Order
from services.order.domain.order_side import OrderSide
from services.order.domain.order_status import OrderStatus
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.command import (
    AcceptOrderCommand,
    CancelOrderCommand,
    CreateOrderCommand,
    ExpireOrderCommand,
    RejectOrderCommand,
    SubmitOrderCommand,
)
from services.order.engine.execution.adapter import ExecutionAdapter
from services.order.engine.execution.gateway import FakeExecutionGateway
from services.order.engine.factory import OrderFactory
from services.order.engine.lifecycle import OrderLifecycle
from services.order.engine.repository import InMemoryOrderRepository
from services.order.engine.service import OrderEngineService
from services.order.engine.validator import OrderValidator
from services.order.request.repository import OrderRequestSnapshot
from services.order.request.state import OrderRequestState

TIMESTAMP = datetime(2026, 8, 13, 9, 30, 0)


def _make_request(
    state: OrderRequestState = OrderRequestState.HANDOFF,
    **overrides,
) -> OrderRequestSnapshot:
    defaults = dict(
        order_request_id="OR-20260813-000001",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="DECISION-001",
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
        idempotency_key="STRAT-001:SESSION-001:INT-001",
        created_at=1000.0,
        state=state,
    )
    defaults.update(overrides)
    return OrderRequestSnapshot(**defaults)


def _make_handoff_request(**overrides) -> OrderRequestSnapshot:
    return _make_request(state=OrderRequestState.HANDOFF, **overrides)


def _make_order(**overrides) -> Order:
    defaults = dict(
        order_id="ORD-20260813-000001",
        order_request_id="OR-20260813-000001",
        client_order_id="ICY-ORD-20260813-000001",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="DECISION-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        limit_price=None,
        status=OrderStatus.CREATED,
        created_at=datetime(2026, 8, 13, 9, 30, 0),
        updated_at=datetime(2026, 8, 13, 9, 30, 0),
    )
    defaults.update(overrides)
    return Order(**defaults)


def _make_create_command(request, **overrides) -> CreateOrderCommand:
    defaults = dict(
        order_request_id=request.order_request_id,
        client_order_id="ICY-ORD-20260813-000001",
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    defaults.update(overrides)
    return CreateOrderCommand(**defaults)


def _make_submit_command(order, **overrides) -> SubmitOrderCommand:
    defaults = dict(
        order_id=order.order_id,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    defaults.update(overrides)
    return SubmitOrderCommand(**defaults)


def _make_accept_command(order, **overrides) -> AcceptOrderCommand:
    defaults = dict(
        order_id=order.order_id,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    defaults.update(overrides)
    return AcceptOrderCommand(**defaults)


def _make_reject_command(order, reason: str = "BROKER_REJECTED", **overrides) -> RejectOrderCommand:
    defaults = dict(
        order_id=order.order_id,
        reason=reason,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    defaults.update(overrides)
    return RejectOrderCommand(**defaults)


def _make_cancel_command(order, **overrides) -> CancelOrderCommand:
    defaults = dict(
        order_id=order.order_id,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    defaults.update(overrides)
    return CancelOrderCommand(**defaults)


def _make_expire_command(order, **overrides) -> ExpireOrderCommand:
    defaults = dict(
        order_id=order.order_id,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    defaults.update(overrides)
    return ExpireOrderCommand(**defaults)


@pytest.fixture
def make_request():
    return _make_request


@pytest.fixture
def make_handoff_request():
    return _make_handoff_request


@pytest.fixture
def make_order():
    return _make_order


@pytest.fixture
def make_create_command():
    return _make_create_command


@pytest.fixture
def make_submit_command():
    return _make_submit_command


@pytest.fixture
def make_accept_command():
    return _make_accept_command


@pytest.fixture
def make_reject_command():
    return _make_reject_command


@pytest.fixture
def make_cancel_command():
    return _make_cancel_command


@pytest.fixture
def make_expire_command():
    return _make_expire_command


@pytest.fixture
def factory() -> OrderFactory:
    return OrderFactory()


@pytest.fixture
def validator() -> OrderValidator:
    return OrderValidator()


@pytest.fixture
def lifecycle() -> OrderLifecycle:
    return OrderLifecycle()


@pytest.fixture
def repository() -> InMemoryOrderRepository:
    return InMemoryOrderRepository()


@pytest.fixture
def gateway() -> FakeExecutionGateway:
    return FakeExecutionGateway()


@pytest.fixture
def adapter(gateway: FakeExecutionGateway) -> ExecutionAdapter:
    return ExecutionAdapter(gateway)


@pytest.fixture
def service(
    repository: InMemoryOrderRepository,
    gateway: FakeExecutionGateway,
) -> OrderEngineService:
    return OrderEngineService(
        repository=repository,
        adapter=ExecutionAdapter(gateway),
    )
