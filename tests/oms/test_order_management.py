"""Tests for OMS/EMS Integration Layer.

Covers:
- Order creation and validation
- Order state machine transitions
- Cancel order flow
- Partial fills and execution tracking
- Broker gateway (paper trading)
- Smart router decision making
- Trade confirmation and reconciliation
- API endpoints
- Error handling and edge cases
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from services.oms.order.models import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    OrderSource,
    TimeInForce,
)
from services.oms.order.state_machine import (
    InvalidTransitionError,
    OrderStateMachine,
)
from services.oms.order.manager import (
    OrderManager,
    OrderModificationError,
    OrderNotFoundError,
    OrderValidationError,
)
from services.oms.gateway.broker_gateway import (
    BrokerGateway,
    BrokerOrderRequest,
    BrokerOrderResponse,
    BrokerType,
    ConnectionStatus,
    PaperTradingGateway,
)
from services.oms.gateway.router import (
    Route,
    RouteMetric,
    SmartRouter,
)
from services.oms.gateway.adapter import BrokerAdapter
from services.oms.execution.tracker import (
    ExecutionTracker,
    ExecutionStatus,
    FillEvent,
    FillEventType,
)
from services.oms.execution.confirmation import (
    TradeConfirmationEngine,
    ConfirmationStatus,
)
from services.oms.api.oms_api import router
from fastapi.testclient import TestClient
from fastapi import FastAPI


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def order_manager():
    """Create a fresh OrderManager for each test."""
    return OrderManager()


@pytest.fixture
def state_machine():
    """Create a fresh OrderStateMachine for each test."""
    return OrderStateMachine()


@pytest.fixture
def sample_order(order_manager):
    """Create a sample order for testing."""
    return order_manager.create_order(
        symbol="NVDA",
        side=OrderSide.BUY,
        quantity=10000,
        price=150.0,
        strategy_id="AI_Momentum",
    )


@pytest.fixture
def execution_tracker():
    """Create a fresh ExecutionTracker for each test."""
    return ExecutionTracker()


@pytest.fixture
def confirmation_engine():
    """Create a fresh TradeConfirmationEngine for each test."""
    return TradeConfirmationEngine()


@pytest.fixture
def smart_router():
    """Create a SmartRouter with test routes."""
    router = SmartRouter()
    router.register_route(Route(
        name="NASDAQ_IBKR",
        broker="IBKR",
        market="NASDAQ",
        fee_bps=0.35,
        latency_ms=5,
        liquidity_score=0.95,
        fill_probability=0.98,
        spread_bps=1.0,
    ))
    router.register_route(Route(
        name="NYSE_LOCAL",
        broker="LOCAL",
        market="NYSE",
        fee_bps=0.50,
        latency_ms=15,
        liquidity_score=0.85,
        fill_probability=0.90,
        spread_bps=2.0,
    ))
    router.register_route(Route(
        name="ARCA_IBKR",
        broker="IBKR",
        market="ARCA",
        fee_bps=0.30,
        latency_ms=8,
        liquidity_score=0.90,
        fill_probability=0.95,
        spread_bps=1.5,
    ))
    return router


@pytest.fixture
def api_client():
    """Create a FastAPI TestClient for API testing."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# =============================================================================
# 1. Order Domain Model Tests
# =============================================================================


class TestOrderModel:
    """Tests for the Order domain model."""

    def test_create_order_basic(self):
        """Test creating a basic order."""
        order = Order(
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
            price=150.0,
        )
        assert order.symbol == "NVDA"
        assert order.side == OrderSide.BUY
        assert order.quantity == 10000
        assert order.price == 150.0
        assert order.status == OrderStatus.CREATED

    def test_create_order_with_all_fields(self, order_manager):
        """Test creating an order with all optional fields."""
        order = order_manager.create_order(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=5000,
            price=175.50,
            order_type=OrderType.LIMIT,
            strategy_id="STRAT_001",
            time_in_force=TimeInForce.GTC,
            source=OrderSource.MANUAL,
            broker="IBKR",
            market="NASDAQ",
        )
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.SELL
        assert order.quantity == 5000
        assert order.price == 175.50
        assert order.order_type == OrderType.LIMIT
        assert order.strategy_id == "STRAT_001"
        assert order.time_in_force == TimeInForce.GTC
        assert order.source == OrderSource.MANUAL
        assert order.broker == "IBKR"
        assert order.market == "NASDAQ"

    def test_order_id_auto_generated(self, order_manager):
        """Test that order IDs are auto-generated."""
        order1 = order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        order2 = order_manager.create_order(symbol="AAPL", side=OrderSide.SELL, quantity=200)
        assert order1.order_id != order2.order_id
        assert order1.order_id.startswith("ORD_")

    def test_remaining_quantity(self):
        """Test remaining_quantity property."""
        order = Order(symbol="NVDA", side=OrderSide.BUY, quantity=10000)
        order.filled_quantity = 3000
        assert order.remaining_quantity == 7000

    def test_fill_pct(self):
        """Test fill_pct property."""
        order = Order(symbol="NVDA", side=OrderSide.BUY, quantity=10000)
        order.filled_quantity = 5000
        assert order.fill_pct == 0.5

        order.filled_quantity = 0
        assert order.fill_pct == 0.0

        order.quantity = 0
        assert order.fill_pct == 0.0

    def test_is_active(self, sample_order):
        """Test is_active property."""
        assert not sample_order.is_active  # CREATED is not active

        sample_order.status = OrderStatus.SUBMITTED
        assert sample_order.is_active

        sample_order.status = OrderStatus.ACKNOWLEDGED
        assert sample_order.is_active

        sample_order.status = OrderStatus.PARTIALLY_FILLED
        assert sample_order.is_active

    def test_is_terminal(self, sample_order):
        """Test is_terminal property."""
        assert not sample_order.is_terminal

        sample_order.status = OrderStatus.FILLED
        assert sample_order.is_terminal

        sample_order.status = OrderStatus.CANCELLED
        assert sample_order.is_terminal

        sample_order.status = OrderStatus.REJECTED
        assert sample_order.is_terminal

    def test_notional_value(self, sample_order):
        """Test notional_value property."""
        assert sample_order.notional_value == 10000 * 150.0

        sample_order.price = 0
        assert sample_order.notional_value == 0.0

    def test_to_dict(self, sample_order):
        """Test order serialization."""
        d = sample_order.to_dict()
        assert d["order_id"] == sample_order.order_id
        assert d["symbol"] == "NVDA"
        assert d["side"] == "BUY"
        assert d["quantity"] == 10000
        assert d["status"] == "CREATED"
        assert d["fill_pct"] == "0.0%"
        assert d["remaining_quantity"] == 10000
        assert d["is_active"] is False
        assert d["is_terminal"] is False

    def test_validation_negative_quantity(self, order_manager):
        """Test that negative quantity is rejected."""
        with pytest.raises(OrderValidationError, match="Quantity must be positive"):
            order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=-100)

    def test_validation_empty_symbol(self, order_manager):
        """Test that empty symbol is rejected."""
        with pytest.raises(OrderValidationError, match="Symbol is required"):
            order_manager.create_order(symbol="", side=OrderSide.BUY, quantity=100)

    def test_validation_limit_order_needs_price(self, order_manager):
        """Test that limit orders require a price."""
        with pytest.raises(OrderValidationError, match="Limit orders require a positive price"):
            order_manager.create_order(
                symbol="NVDA", side=OrderSide.BUY, quantity=100,
                order_type=OrderType.LIMIT, price=0.0,
            )


# =============================================================================
# 2. Order State Machine Tests
# =============================================================================


class TestOrderStateMachine:
    """Tests for the OrderStateMachine."""

    def test_valid_creation_to_validated(self, state_machine, sample_order):
        """Test CREATED -> VALIDATED transition."""
        state_machine.transition(sample_order, OrderStatus.VALIDATED)
        assert sample_order.status == OrderStatus.VALIDATED

    def test_valid_validated_to_routed(self, state_machine, sample_order):
        """Test VALIDATED -> ROUTED transition."""
        state_machine.transition(sample_order, OrderStatus.VALIDATED)
        state_machine.transition(sample_order, OrderStatus.ROUTED)
        assert sample_order.status == OrderStatus.ROUTED

    def test_valid_routed_to_submitted(self, state_machine, sample_order):
        """Test ROUTED -> SUBMITTED transition."""
        state_machine.transition(sample_order, OrderStatus.VALIDATED)
        state_machine.transition(sample_order, OrderStatus.ROUTED)
        state_machine.transition(sample_order, OrderStatus.SUBMITTED)
        assert sample_order.status == OrderStatus.SUBMITTED

    def test_full_happy_path(self, state_machine, sample_order):
        """Test the full CREATED -> FILLED path."""
        transitions = [
            OrderStatus.VALIDATED,
            OrderStatus.ROUTED,
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
        ]
        for status in transitions:
            state_machine.transition(sample_order, status)
        assert sample_order.status == OrderStatus.FILLED

    def test_illegal_transition_filled_to_submitted(self, state_machine, sample_order):
        """Test that FILLED -> SUBMITTED is rejected."""
        sample_order.status = OrderStatus.FILLED
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(sample_order, OrderStatus.SUBMITTED)

    def test_illegal_transition_created_to_filled(self, state_machine, sample_order):
        """Test that CREATED -> FILLED is rejected."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(sample_order, OrderStatus.FILLED)

    def test_illegal_transition_cancelled_to_filled(self, state_machine, sample_order):
        """Test that CANCELLED -> FILLED is rejected."""
        sample_order.status = OrderStatus.CANCELLED
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(sample_order, OrderStatus.FILLED)

    def test_can_transition(self, state_machine):
        """Test can_transition check method."""
        assert state_machine.can_transition(OrderStatus.CREATED, OrderStatus.VALIDATED)
        assert not state_machine.can_transition(OrderStatus.FILLED, OrderStatus.CREATED)
        assert not state_machine.can_transition(OrderStatus.REJECTED, OrderStatus.SUBMITTED)

    def test_get_allowed_transitions(self, state_machine):
        """Test get_allowed_transitions."""
        allowed = state_machine.get_allowed_transitions(OrderStatus.CREATED)
        assert OrderStatus.VALIDATED in allowed
        assert OrderStatus.FILLED not in allowed

        # Terminal states have no transitions
        assert len(state_machine.get_allowed_transitions(OrderStatus.FILLED)) == 0
        assert len(state_machine.get_allowed_transitions(OrderStatus.CANCELLED)) == 0

    def test_is_terminal(self, state_machine):
        """Test is_terminal check."""
        assert not state_machine.is_terminal(OrderStatus.CREATED)
        assert not state_machine.is_terminal(OrderStatus.SUBMITTED)
        assert state_machine.is_terminal(OrderStatus.FILLED)
        assert state_machine.is_terminal(OrderStatus.CANCELLED)
        assert state_machine.is_terminal(OrderStatus.REJECTED)

    def test_partially_filled_to_partially_filled(self, state_machine, sample_order):
        """Test PARTIALLY_FILLED -> PARTIALLY_FILLED (incremental fills)."""
        sample_order.status = OrderStatus.PARTIALLY_FILLED
        state_machine.transition(sample_order, OrderStatus.PARTIALLY_FILLED)
        assert sample_order.status == OrderStatus.PARTIALLY_FILLED

    def test_transition_history_recorded(self, state_machine, sample_order):
        """Test that transitions are recorded in history."""
        state_machine.transition(sample_order, OrderStatus.VALIDATED)
        assert len(sample_order.status_history) >= 2  # CREATED + VALIDATED
        assert sample_order.status_history[-1]["from"] == "CREATED"
        assert sample_order.status_history[-1]["to"] == "VALIDATED"

    def test_transition_labels(self, state_machine):
        """Test human-readable transition labels."""
        label = state_machine.get_transition_label(OrderStatus.CREATED, OrderStatus.VALIDATED)
        assert "validated" in label.lower()

    def test_same_state_transition_rejected(self, state_machine, sample_order):
        """Test that same-state transition is rejected (except PARTIALLY_FILLED)."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(sample_order, OrderStatus.CREATED)


# =============================================================================
# 3. Order Manager Tests
# =============================================================================


class TestOrderManager:
    """Tests for the OrderManager."""

    def test_create_order(self, order_manager):
        """Test basic order creation via manager."""
        order = order_manager.create_order(
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
            strategy_id="STRAT_001",
        )
        assert order.status == OrderStatus.CREATED
        assert order.symbol == "NVDA"
        assert order.quantity == 10000

    def test_validate_order(self, order_manager, sample_order):
        """Test order validation."""
        order = order_manager.validate_order(sample_order.order_id)
        assert order.status == OrderStatus.VALIDATED

    def test_route_order(self, order_manager, sample_order):
        """Test order routing."""
        order_manager.validate_order(sample_order.order_id)
        order = order_manager.route_order(
            sample_order.order_id,
            broker="IBKR",
            market="NASDAQ",
        )
        assert order.status == OrderStatus.ROUTED
        assert order.broker == "IBKR"
        assert order.market == "NASDAQ"

    def test_submit_order(self, order_manager, sample_order):
        """Test order submission."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order = order_manager.submit_order(sample_order.order_id)
        assert order.status == OrderStatus.SUBMITTED
        assert order.submitted_at is not None

    def test_acknowledge_order(self, order_manager, sample_order):
        """Test order acknowledgement."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order = order_manager.acknowledge_order(sample_order.order_id)
        assert order.status == OrderStatus.ACKNOWLEDGED

    def test_fill_order_full(self, order_manager, sample_order):
        """Test full order fill."""
        # Move to ACKNOWLEDGED first
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)

        order = order_manager.fill_order(
            sample_order.order_id,
            fill_quantity=10000,
            fill_price=150.5,
        )
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10000
        assert order.average_fill_price == 150.5
        assert order.filled_at is not None

    def test_fill_order_partial(self, order_manager, sample_order):
        """Test partial order fill."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)

        order = order_manager.fill_order(
            sample_order.order_id,
            fill_quantity=3000,
            fill_price=150.0,
        )
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == 3000
        assert order.remaining_quantity == 7000

        # Second partial fill
        order = order_manager.fill_order(
            sample_order.order_id,
            fill_quantity=7000,
            fill_price=151.0,
        )
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10000
        # Weighted average: (3000*150 + 7000*151) / 10000
        expected_avg = (3000 * 150.0 + 7000 * 151.0) / 10000
        assert abs(order.average_fill_price - expected_avg) < 0.01

    def test_cancel_order_created(self, order_manager, sample_order):
        """Test cancelling an order in CREATED state."""
        order = order_manager.cancel_order(sample_order.order_id, reason="No longer needed")
        assert order.status == OrderStatus.CANCELLED
        assert order.cancelled_at is not None

    def test_cancel_order_submitted(self, order_manager, sample_order):
        """Test cancelling an order in SUBMITTED state."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)

        order = order_manager.cancel_order(sample_order.order_id)
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_partially_filled_order(self, order_manager, sample_order):
        """Test cancelling a partially filled order."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)
        order_manager.fill_order(sample_order.order_id, fill_quantity=5000, fill_price=150.0)

        order = order_manager.cancel_order(sample_order.order_id, reason="Risk limit reached")
        assert order.status == OrderStatus.CANCELLED
        assert order.filled_quantity == 5000

    def test_reject_order(self, order_manager, sample_order):
        """Test order rejection."""
        order_manager.validate_order(sample_order.order_id)
        order = order_manager.reject_order(
            sample_order.order_id,
            reason="Symbol not tradeable",
        )
        assert order.status == OrderStatus.REJECTED
        assert order.rejection_reason == "Symbol not tradeable"

    def test_replace_order_quantity(self, order_manager, sample_order):
        """Test replacing order quantity."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)

        order = order_manager.replace_order(sample_order.order_id, new_quantity=15000)
        assert order.quantity == 15000

    def test_replace_order_price(self, order_manager, sample_order):
        """Test replacing order price."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)

        order = order_manager.replace_order(sample_order.order_id, new_price=155.0)
        assert order.price == 155.0

    def test_replace_filled_order_denied(self, order_manager, sample_order):
        """Test that replacing a filled order is denied."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)
        order_manager.fill_order(sample_order.order_id, fill_quantity=10000, fill_price=150.0)

        with pytest.raises(OrderModificationError):
            order_manager.replace_order(sample_order.order_id, new_quantity=15000)

    def test_replace_below_filled_quantity_denied(self, order_manager, sample_order):
        """Test that new quantity cannot be below filled quantity."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)
        order_manager.fill_order(sample_order.order_id, fill_quantity=5000, fill_price=150.0)

        with pytest.raises(OrderModificationError):
            order_manager.replace_order(sample_order.order_id, new_quantity=3000)

    def test_get_order_status(self, order_manager, sample_order):
        """Test getting order status."""
        status = order_manager.get_order_status(sample_order.order_id)
        assert status == OrderStatus.CREATED

        status = order_manager.get_order_status("nonexistent")
        assert status is None

    def test_get_orders_by_symbol(self, order_manager):
        """Test filtering orders by symbol."""
        order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        order_manager.create_order(symbol="NVDA", side=OrderSide.SELL, quantity=200)
        order_manager.create_order(symbol="AAPL", side=OrderSide.BUY, quantity=300)

        nvda_orders = order_manager.get_orders_by_symbol("NVDA")
        assert len(nvda_orders) == 2

        aapl_orders = order_manager.get_orders_by_symbol("AAPL")
        assert len(aapl_orders) == 1

        # Case insensitive
        tsla_orders = order_manager.get_orders_by_symbol("nvda")
        assert len(tsla_orders) == 2

    def test_get_orders_by_strategy(self, order_manager):
        """Test filtering orders by strategy."""
        order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100, strategy_id="S1")
        order_manager.create_order(symbol="AAPL", side=OrderSide.BUY, quantity=200, strategy_id="S1")
        order_manager.create_order(symbol="TSLA", side=OrderSide.SELL, quantity=300, strategy_id="S2")

        s1_orders = order_manager.get_orders_by_strategy("S1")
        assert len(s1_orders) == 2

        s2_orders = order_manager.get_orders_by_strategy("S2")
        assert len(s2_orders) == 1

    def test_get_orders_by_status(self, order_manager):
        """Test filtering orders by status."""
        o1 = order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        o2 = order_manager.create_order(symbol="AAPL", side=OrderSide.SELL, quantity=200)

        created = order_manager.get_orders_by_status(OrderStatus.CREATED)
        assert len(created) == 2

        order_manager.cancel_order(o1.order_id)
        cancelled = order_manager.get_orders_by_status(OrderStatus.CANCELLED)
        assert len(cancelled) == 1

    def test_get_active_orders(self, order_manager):
        """Test getting active orders."""
        o1 = order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        o2 = order_manager.create_order(symbol="AAPL", side=OrderSide.SELL, quantity=200)

        assert len(order_manager.get_active_orders()) == 0

        # Move o1 to active state
        order_manager.validate_order(o1.order_id)
        order_manager.route_order(o1.order_id, broker="IBKR")
        order_manager.submit_order(o1.order_id)
        assert len(order_manager.get_active_orders()) == 1

    def test_get_order_summary(self, order_manager):
        """Test order summary."""
        o1 = order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        o2 = order_manager.create_order(symbol="AAPL", side=OrderSide.SELL, quantity=200)
        order_manager.cancel_order(o1.order_id)

        summary = order_manager.get_order_summary()
        assert summary["total"] == 2
        assert summary["by_status"]["CREATED"] == 1
        assert summary["by_status"]["CANCELLED"] == 1

    def test_order_not_found(self, order_manager):
        """Test error handling for non-existent orders."""
        with pytest.raises(OrderNotFoundError):
            order_manager.validate_order("nonexistent")
        with pytest.raises(OrderNotFoundError):
            order_manager.cancel_order("nonexistent")


# =============================================================================
# 4. Broker Gateway Tests
# =============================================================================


class TestBrokerGateway:
    """Tests for broker gateway implementations."""

    @pytest.mark.asyncio
    async def test_paper_gateway_connect(self):
        """Test paper trading gateway connection."""
        gateway = PaperTradingGateway()
        assert gateway.connection_status == ConnectionStatus.DISCONNECTED

        result = await gateway.connect()
        assert result is True
        assert gateway.connection_status == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_paper_gateway_disconnect(self):
        """Test paper trading gateway disconnection."""
        gateway = PaperTradingGateway()
        await gateway.connect()
        await gateway.disconnect()
        assert gateway.connection_status == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_paper_gateway_is_connected(self):
        """Test connection status check."""
        gateway = PaperTradingGateway()
        assert not await gateway.is_connected()
        await gateway.connect()
        assert await gateway.is_connected()

    @pytest.mark.asyncio
    async def test_paper_gateway_submit_order(self):
        """Test order submission via paper gateway."""
        gateway = PaperTradingGateway()
        await gateway.connect()

        request = BrokerOrderRequest(
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            price=150.0,
            client_order_id="ORD_001",
        )

        response = await gateway.submit_order(request)
        assert response.broker_order_id.startswith("BRK_")
        assert response.client_order_id == "ORD_001"
        assert response.status == "FILLED"
        assert response.filled_quantity == 10000

    @pytest.mark.asyncio
    async def test_paper_gateway_submit_without_connection(self):
        """Test submission without connection raises error."""
        gateway = PaperTradingGateway()
        request = BrokerOrderRequest(symbol="NVDA", side="BUY", quantity=100)

        with pytest.raises(ConnectionError):
            await gateway.submit_order(request)

    @pytest.mark.asyncio
    async def test_paper_gateway_cancel_order(self):
        """Test order cancellation via paper gateway."""
        gateway = PaperTradingGateway()
        await gateway.connect()

        request = BrokerOrderRequest(
            symbol="NVDA", side="BUY", quantity=10000,
            client_order_id="ORD_001",
        )
        submit_resp = await gateway.submit_order(request)

        cancel_resp = await gateway.cancel_order(submit_resp.broker_order_id)
        assert cancel_resp.status == "CANCELLED"

    @pytest.mark.asyncio
    async def test_paper_gateway_cancel_nonexistent(self):
        """Test cancelling non-existent order."""
        gateway = PaperTradingGateway()
        await gateway.connect()

        response = await gateway.cancel_order("nonexistent")
        assert response.status == "ERROR"

    @pytest.mark.asyncio
    async def test_paper_gateway_replace_order(self):
        """Test order replacement via paper gateway."""
        gateway = PaperTradingGateway()
        await gateway.connect()

        request = BrokerOrderRequest(
            symbol="NVDA", side="BUY", quantity=10000,
            client_order_id="ORD_001",
        )
        submit_resp = await gateway.submit_order(request)

        replace_resp = await gateway.replace_order(
            submit_resp.broker_order_id,
            new_quantity=15000,
        )
        assert replace_resp.status == "REPLACED"

    @pytest.mark.asyncio
    async def test_paper_gateway_query_positions(self):
        """Test position query after trades."""
        gateway = PaperTradingGateway()
        await gateway.connect()

        # Submit a BUY order
        request = BrokerOrderRequest(symbol="NVDA", side="BUY", quantity=10000, price=150.0)
        await gateway.submit_order(request)

        positions = await gateway.query_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "NVDA"
        assert positions[0].quantity == 10000

    @pytest.mark.asyncio
    async def test_paper_gateway_query_balance(self):
        """Test balance query."""
        gateway = PaperTradingGateway(initial_balance=500000)
        await gateway.connect()

        balance = await gateway.query_balance()
        assert balance.total_cash == 500000
        assert balance.account_id == "PAPER_001"

    @pytest.mark.asyncio
    async def test_paper_gateway_market_data(self):
        """Test market data query."""
        gateway = PaperTradingGateway()
        await gateway.connect()

        data = await gateway.get_market_data("NVDA")
        assert data["symbol"] == "NVDA"
        assert "bid" in data
        assert "ask" in data
        assert "last_price" in data

    @pytest.mark.asyncio
    async def test_broker_adapter_to_broker_request(self):
        """Test adapter conversion OMS -> Broker."""
        gateway = PaperTradingGateway()
        adapter = BrokerAdapter(gateway=gateway, account_id="ACC_001")

        order = Order(
            order_id="ORD_001",
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
            price=150.0,
            strategy_id="S1",
        )

        request = adapter.to_broker_request(order)
        assert request.symbol == "NVDA"
        assert request.side == "BUY"
        assert request.quantity == 10000
        assert request.account_id == "ACC_001"
        assert request.client_order_id == "ORD_001"
        assert request.metadata["strategy_id"] == "S1"

    @pytest.mark.asyncio
    async def test_broker_adapter_apply_fill(self):
        """Test adapter applying broker fill to OMS order."""
        gateway = PaperTradingGateway()
        adapter = BrokerAdapter(gateway=gateway)

        order = Order(
            order_id="ORD_001",
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
        )

        response = BrokerOrderResponse(
            broker_order_id="BRK_001",
            client_order_id="ORD_001",
            status="FILLED",
            filled_quantity=5000,
            average_price=150.5,
            commission=2.50,
        )

        order = adapter.apply_fill(order, response)
        assert order.filled_quantity == 5000
        assert order.average_fill_price == 150.5
        assert order.total_commission == 2.50


# =============================================================================
# 5. Smart Router Tests
# =============================================================================


class TestSmartRouter:
    """Tests for the SmartRouter."""

    def test_register_route(self, smart_router):
        """Test registering routes."""
        assert len(smart_router.routes) == 3
        assert "NASDAQ_IBKR" in smart_router.routes

    def test_remove_route(self, smart_router):
        """Test removing a route."""
        smart_router.remove_route("NYSE_LOCAL")
        assert len(smart_router.routes) == 2
        assert "NYSE_LOCAL" not in smart_router.routes

    def test_get_available_routes(self, smart_router):
        """Test filtering available routes."""
        routes = smart_router.get_available_routes()
        assert len(routes) == 3

    def test_get_available_routes_closed_market(self, smart_router):
        """Test that closed markets are excluded."""
        closed_route = Route(
            name="CLOSED_MARKET",
            broker="IBKR",
            market="TEST",
            is_open=False,
        )
        smart_router.register_route(closed_route)

        routes = smart_router.get_available_routes()
        assert len(routes) == 3  # Only the 3 open routes
        assert "CLOSED_MARKET" not in [r.name for r in routes]

    def test_get_available_routes_quantity_filter(self, smart_router):
        """Test filtering by quantity."""
        limited_route = Route(
            name="LIMITED_ROUTE",
            broker="IBKR",
            market="LIMITED",
            max_order_size=100,
        )
        smart_router.register_route(limited_route)

        routes = smart_router.get_available_routes(quantity=1000)
        assert "LIMITED_ROUTE" not in [r.name for r in routes]

        routes = smart_router.get_available_routes(quantity=50)
        assert "LIMITED_ROUTE" in [r.name for r in routes]

    def test_route_selection(self, smart_router):
        """Test that the router selects the best route."""
        decision = smart_router.route(order_id="ORD_001", symbol="NVDA", quantity=10000)

        assert decision.selected_route is not None
        assert decision.score > 0
        assert len(decision.alternative_routes) == 2
        # NASDAQ_IBKR should win (lowest fee, highest liquidity, best fill prob)
        assert decision.selected_route.name == "NASDAQ_IBKR"

    def test_route_with_preferred_broker(self, smart_router):
        """Test routing with preferred broker."""
        decision = smart_router.route(
            order_id="ORD_001",
            symbol="NVDA",
            quantity=10000,
            preferred_broker="LOCAL",
        )
        assert decision.selected_route.broker == "LOCAL"
        assert decision.selected_route.name == "NYSE_LOCAL"

    def test_route_no_routes_available(self, smart_router):
        """Test routing when no routes are available."""
        empty_router = SmartRouter()
        with pytest.raises(ValueError, match="No available routes"):
            empty_router.route(order_id="ORD_001", symbol="NVDA")

    def test_set_weights_validation(self, smart_router):
        """Test weight validation."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            smart_router.set_weights({
                RouteMetric.FEE: 0.5,
                RouteMetric.LATENCY: 0.3,
            })

    def test_set_weights(self, smart_router):
        """Test setting valid weights."""
        new_weights = {
            RouteMetric.FEE: 0.10,
            RouteMetric.LATENCY: 0.10,
            RouteMetric.LIQUIDITY: 0.30,
            RouteMetric.FILL_PROBABILITY: 0.30,
            RouteMetric.SPREAD: 0.20,
        }
        smart_router.set_weights(new_weights)
        assert smart_router.weights[RouteMetric.FEE] == 0.10

    def test_routing_decision_format(self, smart_router):
        """Test the routing decision structure."""
        decision = smart_router.route(order_id="ORD_001", symbol="NVDA", quantity=10000)
        assert decision.order_id == "ORD_001"
        assert "Route" in decision.reason
        assert decision.score > 0


# =============================================================================
# 6. Execution Tracker Tests
# =============================================================================


class TestExecutionTracker:
    """Tests for the ExecutionTracker."""

    def test_start_tracking(self, execution_tracker):
        """Test starting to track an order."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000, arrival_price=150.0)
        snapshot = execution_tracker.get_snapshot("ORD_001")
        assert snapshot is not None
        assert snapshot.symbol == "NVDA"
        assert snapshot.side == "BUY"
        assert snapshot.total_quantity == 100000
        assert snapshot.filled_quantity == 0
        assert snapshot.status == ExecutionStatus.PENDING

    def test_on_fill_single(self, execution_tracker):
        """Test recording a single fill."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)

        fill = FillEvent(order_id="ORD_001", fill_id="F001", quantity=30000, price=150.0)
        execution_tracker.on_fill(fill)

        snapshot = execution_tracker.get_snapshot("ORD_001")
        assert snapshot.filled_quantity == 30000
        assert snapshot.remaining_quantity == 70000
        assert snapshot.fill_pct == 0.3
        assert snapshot.status == ExecutionStatus.EXECUTING

    def test_on_fill_multiple(self, execution_tracker):
        """Test recording multiple partial fills."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)

        fills = [
            FillEvent(order_id="ORD_001", fill_id="F001", quantity=30000, price=150.0),
            FillEvent(order_id="ORD_001", fill_id="F002", quantity=70000, price=151.0),
        ]
        for f in fills:
            execution_tracker.on_fill(f)

        snapshot = execution_tracker.get_snapshot("ORD_001")
        assert snapshot.filled_quantity == 100000
        assert snapshot.status == ExecutionStatus.COMPLETED
        assert snapshot.fill_count == 2

    def test_average_price_calculation(self, execution_tracker):
        """Test VWAP calculation."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)

        fills = [
            FillEvent(order_id="ORD_001", fill_id="F001", quantity=50000, price=150.0),
            FillEvent(order_id="ORD_001", fill_id="F002", quantity=50000, price=152.0),
        ]
        for f in fills:
            execution_tracker.on_fill(f)

        snapshot = execution_tracker.get_snapshot("ORD_001")
        assert snapshot.average_price == 151.0  # (50000*150 + 50000*152) / 100000

    def test_slippage_calculation_buy(self, execution_tracker):
        """Test slippage calculation for BUY orders."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000, arrival_price=150.0)

        fill = FillEvent(order_id="ORD_001", fill_id="F001", quantity=100000, price=151.0)
        execution_tracker.on_fill(fill)

        snapshot = execution_tracker.get_snapshot("ORD_001")
        # Slippage = (151 - 150) / 150 * 10000 = 66.67 bps
        assert abs(snapshot.slippage_bps - 66.67) < 1.0

    def test_slippage_calculation_sell(self, execution_tracker):
        """Test slippage calculation for SELL orders."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "SELL", 100000, arrival_price=150.0)

        fill = FillEvent(order_id="ORD_001", fill_id="F001", quantity=100000, price=149.0)
        execution_tracker.on_fill(fill)

        snapshot = execution_tracker.get_snapshot("ORD_001")
        # Slippage = (150 - 149) / 150 * 10000 = 66.67 bps
        assert abs(snapshot.slippage_bps - 66.67) < 1.0

    def test_on_fill_untracked_order(self, execution_tracker):
        """Test that filling untracked order raises error."""
        fill = FillEvent(order_id="nonexistent", fill_id="F001", quantity=100, price=150.0)
        with pytest.raises(ValueError, match="not being tracked"):
            execution_tracker.on_fill(fill)

    def test_get_fills(self, execution_tracker):
        """Test getting all fills for an order."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)

        fills = [
            FillEvent(order_id="ORD_001", fill_id="F001", quantity=30000, price=150.0),
            FillEvent(order_id="ORD_001", fill_id="F002", quantity=20000, price=151.0),
        ]
        for f in fills:
            execution_tracker.on_fill(f)

        all_fills = execution_tracker.get_fills("ORD_001")
        assert len(all_fills) == 2
        assert all_fills[0].fill_id == "F001"

    def test_get_report(self, execution_tracker):
        """Test generating an execution report."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000, arrival_price=150.0)

        fill = FillEvent(order_id="ORD_001", fill_id="F001", quantity=100000, price=151.0, commission=5.0)
        execution_tracker.on_fill(fill)

        report = execution_tracker.get_report("ORD_001")
        assert report is not None
        assert report.filled_quantity == 100000
        assert report.total_cost == 100000 * 151.0 + 5.0
        assert report.execution_time_seconds >= 0

    def test_get_report_nonexistent(self, execution_tracker):
        """Test report for non-existent order."""
        report = execution_tracker.get_report("nonexistent")
        assert report is None

    def test_get_active_orders(self, execution_tracker):
        """Test getting active orders."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)
        execution_tracker.start_tracking("ORD_002", "AAPL", "SELL", 50000)

        fill = FillEvent(order_id="ORD_001", fill_id="F001", quantity=30000, price=150.0)
        execution_tracker.on_fill(fill)

        active = execution_tracker.get_active_orders()
        assert "ORD_001" in active
        assert "ORD_002" not in active  # Not yet executing

    def test_get_all_snapshots(self, execution_tracker):
        """Test getting all snapshots."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)
        execution_tracker.start_tracking("ORD_002", "AAPL", "SELL", 50000)

        snapshots = execution_tracker.get_all_snapshots()
        assert len(snapshots) == 2

    def test_commission_tracking(self, execution_tracker):
        """Test commission is tracked correctly."""
        execution_tracker.start_tracking("ORD_001", "NVDA", "BUY", 100000)

        fills = [
            FillEvent(order_id="ORD_001", fill_id="F001", quantity=50000, price=150.0, commission=2.50),
            FillEvent(order_id="ORD_001", fill_id="F002", quantity=50000, price=151.0, commission=2.50),
        ]
        for f in fills:
            execution_tracker.on_fill(f)

        snapshot = execution_tracker.get_snapshot("ORD_001")
        assert snapshot.total_commission == 5.0


# =============================================================================
# 7. Trade Confirmation Tests
# =============================================================================


class TestTradeConfirmation:
    """Tests for the TradeConfirmationEngine."""

    def test_confirm_trade(self, confirmation_engine):
        """Test confirming a trade."""
        confirmation = confirmation_engine.confirm(
            order_id="ORD_001",
            broker_order_id="BRK_001",
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            price=150.0,
            commission=2.50,
        )
        assert confirmation.order_id == "ORD_001"
        assert confirmation.symbol == "NVDA"
        assert confirmation.quantity == 10000
        assert confirmation.price == 150.0
        assert confirmation.commission == 2.50
        assert confirmation.notional == 1500000.0
        assert confirmation.total_cost == 1500002.50
        assert confirmation.status == ConfirmationStatus.PENDING

    def test_get_confirmation(self, confirmation_engine):
        """Test retrieving a confirmation."""
        confirmation = confirmation_engine.confirm(
            order_id="ORD_001",
            broker_order_id="BRK_001",
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            price=150.0,
        )

        retrieved = confirmation_engine.get_confirmation(confirmation.confirmation_id)
        assert retrieved is not None
        assert retrieved.order_id == "ORD_001"

    def test_get_confirmations_by_order(self, confirmation_engine):
        """Test getting confirmations for a specific order."""
        confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=5000, price=150.0,
        )
        confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_002",
            symbol="NVDA", side="BUY", quantity=5000, price=151.0,
        )

        confirmations = confirmation_engine.get_confirmations_by_order("ORD_001")
        assert len(confirmations) == 2

    def test_register_handler(self, confirmation_engine):
        """Test registering and calling handlers."""
        received = []

        def test_handler(confirmation):
            received.append(confirmation)

        confirmation_engine.register_handler("test", test_handler)

        confirmation = confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0,
        )
        assert len(received) == 1
        assert received[0].order_id == "ORD_001"
        assert confirmation.status == ConfirmationStatus.CONFIRMED

    def test_unregister_handler(self, confirmation_engine):
        """Test unregistering a handler."""
        received = []

        def test_handler(confirmation):
            received.append(confirmation)

        confirmation_engine.register_handler("test", test_handler)
        confirmation_engine.unregister_handler("test")

        confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0,
        )
        assert len(received) == 0

    def test_reconcile_matching(self, confirmation_engine):
        """Test reconciliation with matching records."""
        confirmation = confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0,
        )

        matched = confirmation_engine.reconcile(
            confirmation.confirmation_id,
            {"quantity": 10000, "price": 150.0},
        )
        assert matched is True
        assert confirmation.status == ConfirmationStatus.RECONCILED

    def test_reconcile_mismatch(self, confirmation_engine):
        """Test reconciliation with mismatching records."""
        confirmation = confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0,
        )

        matched = confirmation_engine.reconcile(
            confirmation.confirmation_id,
            {"quantity": 9500, "price": 150.0},
        )
        assert matched is False
        assert confirmation.status == ConfirmationStatus.DISCREPANCY

    def test_reconcile_nonexistent(self, confirmation_engine):
        """Test reconciling non-existent confirmation."""
        matched = confirmation_engine.reconcile(
            "nonexistent",
            {"quantity": 10000, "price": 150.0},
        )
        assert matched is False

    def test_get_pending_confirmations(self, confirmation_engine):
        """Test getting pending confirmations."""
        confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0,
        )
        pending = confirmation_engine.get_pending_confirmations()
        assert len(pending) == 1

    def test_get_discrepancies(self, confirmation_engine):
        """Test getting discrepancy confirmations."""
        confirmation = confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0,
        )
        confirmation_engine.reconcile(
            confirmation.confirmation_id,
            {"quantity": 9000, "price": 150.0},
        )

        discrepancies = confirmation_engine.get_discrepancies()
        assert len(discrepancies) == 1

    def test_confirmation_to_dict(self, confirmation_engine):
        """Test confirmation serialization."""
        confirmation = confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=10000, price=150.0, commission=2.50,
            exchange="NASDAQ",
        )
        d = confirmation.to_dict()
        assert d["order_id"] == "ORD_001"
        assert d["symbol"] == "NVDA"
        assert d["notional"] == 1500000.0
        assert d["total_cost"] == 1500002.50
        assert d["exchange"] == "NASDAQ"


# =============================================================================
# 8. API Endpoint Tests
# =============================================================================


class TestOMSAPI:
    """Tests for the OMS REST API endpoints."""

    def test_create_order_endpoint(self, api_client):
        """Test POST /api/v1/orders."""
        response = api_client.post(
            "/api/v1/orders",
            params={
                "symbol": "NVDA",
                "side": "BUY",
                "quantity": 10000,
                "strategy_id": "AI_Momentum",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "NVDA"
        assert data["side"] == "BUY"
        assert data["quantity"] == 10000
        assert data["status"] == "CREATED"

    def test_create_order_validation_error(self, api_client):
        """Test that invalid orders return 400."""
        response = api_client.post(
            "/api/v1/orders",
            params={
                "symbol": "",
                "side": "BUY",
                "quantity": 100,
            },
        )
        assert response.status_code == 400

    def test_get_order_endpoint(self, api_client):
        """Test GET /api/v1/orders/{order_id}."""
        # First create an order
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]

        # Then get it
        response = api_client.get(f"/api/v1/orders/{order_id}")
        assert response.status_code == 200
        assert response.json()["order_id"] == order_id

    def test_get_order_not_found(self, api_client):
        """Test GET non-existent order returns 404."""
        response = api_client.get("/api/v1/orders/nonexistent")
        assert response.status_code == 404

    def test_cancel_order_endpoint(self, api_client):
        """Test POST /api/v1/orders/{order_id}/cancel."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]

        response = api_client.post(
            f"/api/v1/orders/{order_id}/cancel",
            params={"reason": "No longer needed"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_replace_order_endpoint(self, api_client):
        """Test POST /api/v1/orders/{order_id}/replace."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]

        # Need to move to SUBMITTED state first
        api_client.post(f"/api/v1/orders/{order_id}/validate")
        api_client.post(f"/api/v1/orders/{order_id}/route", params={"broker": "IBKR"})
        api_client.post(f"/api/v1/orders/{order_id}/submit")

        response = api_client.post(
            f"/api/v1/orders/{order_id}/replace",
            params={"new_quantity": 15000},
        )
        assert response.status_code == 200
        assert response.json()["quantity"] == 15000

    def test_validate_order_endpoint(self, api_client):
        """Test POST /api/v1/orders/{order_id}/validate."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]

        response = api_client.post(f"/api/v1/orders/{order_id}/validate")
        assert response.status_code == 200
        assert response.json()["status"] == "VALIDATED"

    def test_route_order_endpoint(self, api_client):
        """Test POST /api/v1/orders/{order_id}/route."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]
        api_client.post(f"/api/v1/orders/{order_id}/validate")

        response = api_client.post(
            f"/api/v1/orders/{order_id}/route",
            params={"broker": "IBKR", "market": "NASDAQ"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ROUTED"
        assert response.json()["broker"] == "IBKR"

    def test_submit_order_endpoint(self, api_client):
        """Test POST /api/v1/orders/{order_id}/submit."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]
        api_client.post(f"/api/v1/orders/{order_id}/validate")
        api_client.post(f"/api/v1/orders/{order_id}/route", params={"broker": "IBKR"})

        response = api_client.post(f"/api/v1/orders/{order_id}/submit")
        assert response.status_code == 200
        assert response.json()["status"] == "SUBMITTED"

    def test_fill_order_endpoint(self, api_client):
        """Test POST /api/v1/orders/{order_id}/fill."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]
        api_client.post(f"/api/v1/orders/{order_id}/validate")
        api_client.post(f"/api/v1/orders/{order_id}/route", params={"broker": "IBKR"})
        api_client.post(f"/api/v1/orders/{order_id}/submit")
        api_client.post(f"/api/v1/orders/{order_id}/acknowledge")

        response = api_client.post(
            f"/api/v1/orders/{order_id}/fill",
            params={"fill_quantity": 5000, "fill_price": 150.0},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "PARTIALLY_FILLED"
        assert response.json()["filled_quantity"] == 5000

    def test_execution_snapshot_endpoint(self, api_client):
        """Test GET /api/v1/orders/{order_id}/snapshot."""
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]
        api_client.post(f"/api/v1/orders/{order_id}/validate")
        api_client.post(f"/api/v1/orders/{order_id}/route", params={"broker": "IBKR"})
        api_client.post(f"/api/v1/orders/{order_id}/submit")
        api_client.post(f"/api/v1/orders/{order_id}/acknowledge")
        api_client.post(
            f"/api/v1/orders/{order_id}/fill",
            params={"fill_quantity": 5000, "fill_price": 150.0},
        )

        response = api_client.get(f"/api/v1/orders/{order_id}/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == order_id
        assert data["filled_quantity"] == 5000

    def test_active_orders_endpoint(self, api_client):
        """Test GET /api/v1/orders/active."""
        # Create and submit an order
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]
        api_client.post(f"/api/v1/orders/{order_id}/validate")
        api_client.post(f"/api/v1/orders/{order_id}/route", params={"broker": "IBKR"})
        api_client.post(f"/api/v1/orders/{order_id}/submit")

        response = api_client.get("/api/v1/orders/active")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1

    def test_orders_summary_endpoint(self, api_client):
        """Test GET /api/v1/orders/summary."""
        api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )

        response = api_client.get("/api/v1/orders/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert "by_status" in data

    def test_confirmations_endpoint(self, api_client):
        """Test GET /api/v1/confirmations/{order_id}."""
        # Create and fill an order to generate confirmations
        create_resp = api_client.post(
            "/api/v1/orders",
            params={"symbol": "NVDA", "side": "BUY", "quantity": 10000},
        )
        order_id = create_resp.json()["order_id"]
        api_client.post(f"/api/v1/orders/{order_id}/validate")
        api_client.post(f"/api/v1/orders/{order_id}/route", params={"broker": "IBKR"})
        api_client.post(f"/api/v1/orders/{order_id}/submit")
        api_client.post(f"/api/v1/orders/{order_id}/acknowledge")
        api_client.post(
            f"/api/v1/orders/{order_id}/fill",
            params={"fill_quantity": 5000, "fill_price": 150.0},
        )

        response = api_client.get(f"/api/v1/confirmations/{order_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == order_id
        assert data["count"] >= 1


# =============================================================================
# 9. Edge Cases & Error Handling
# =============================================================================


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_fill_quantity_exceeds_order_quantity(self, order_manager, sample_order):
        """Test that filling more than order quantity still works (marks as FILLED)."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)

        # Fill more than requested
        order = order_manager.fill_order(
            sample_order.order_id,
            fill_quantity=12000,
            fill_price=150.0,
        )
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 12000

    def test_zero_quantity_fill_rejected(self, order_manager, sample_order):
        """Test that zero quantity fill is rejected."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)

        with pytest.raises(OrderValidationError, match="Fill quantity must be positive"):
            order_manager.fill_order(sample_order.order_id, fill_quantity=0, fill_price=150.0)

    def test_negative_fill_price_rejected(self, order_manager, sample_order):
        """Test that negative fill price is rejected."""
        order_manager.validate_order(sample_order.order_id)
        order_manager.route_order(sample_order.order_id, broker="IBKR")
        order_manager.submit_order(sample_order.order_id)
        order_manager.acknowledge_order(sample_order.order_id)

        with pytest.raises(OrderValidationError, match="Fill price must be positive"):
            order_manager.fill_order(sample_order.order_id, fill_quantity=100, fill_price=-1.0)

    def test_router_with_no_routes(self):
        """Test router behavior with no routes registered."""
        router = SmartRouter()
        with pytest.raises(ValueError, match="No available routes"):
            router.route(order_id="ORD_001")

    def test_multiple_cancels(self, order_manager, sample_order):
        """Test that cancelling an already cancelled order fails."""
        order_manager.cancel_order(sample_order.order_id)

        with pytest.raises(InvalidTransitionError):
            order_manager.cancel_order(sample_order.order_id)

    def test_fill_cancelled_order_rejected(self, order_manager, sample_order):
        """Test that filling a cancelled order fails."""
        order_manager.cancel_order(sample_order.order_id)

        with pytest.raises(InvalidTransitionError):
            order_manager.fill_order(sample_order.order_id, fill_quantity=100, fill_price=150.0)

    def test_get_snapshot_untracked_order(self, execution_tracker):
        """Test getting snapshot for untracked order."""
        snapshot = execution_tracker.get_snapshot("nonexistent")
        assert snapshot is None

    def test_get_confirmation_nonexistent(self, confirmation_engine):
        """Test getting non-existent confirmation."""
        confirmation = confirmation_engine.get_confirmation("nonexistent")
        assert confirmation is None

    def test_order_count(self, order_manager):
        """Test order count tracking."""
        assert order_manager.get_order_count() == 0
        order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        assert order_manager.get_order_count() == 1
        order_manager.create_order(symbol="AAPL", side=OrderSide.SELL, quantity=200)
        assert order_manager.get_order_count() == 2

    def test_get_all_orders(self, order_manager):
        """Test getting all orders."""
        order_manager.create_order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        order_manager.create_order(symbol="AAPL", side=OrderSide.SELL, quantity=200)

        all_orders = order_manager.get_all_orders()
        assert len(all_orders) == 2

    def test_get_confirmations_by_order_empty(self, confirmation_engine):
        """Test getting confirmations for order with no trades."""
        confirmations = confirmation_engine.get_confirmations_by_order("ORD_NONE")
        assert len(confirmations) == 0

    def test_get_all_confirmations(self, confirmation_engine):
        """Test getting all confirmations."""
        confirmation_engine.confirm(
            order_id="ORD_001", broker_order_id="BRK_001",
            symbol="NVDA", side="BUY", quantity=5000, price=150.0,
        )
        confirmation_engine.confirm(
            order_id="ORD_002", broker_order_id="BRK_002",
            symbol="AAPL", side="SELL", quantity=3000, price=175.0,
        )
        all_confirmations = confirmation_engine.get_all_confirmations()
        assert len(all_confirmations) == 2

    def test_broker_adapter_cancel_request(self):
        """Test broker adapter creating cancel request."""
        gateway = PaperTradingGateway()
        adapter = BrokerAdapter(gateway=gateway)

        order = Order(
            order_id="ORD_001",
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
            filled_quantity=3000,
        )

        request = adapter.to_cancel_request(order)
        assert request.quantity == 7000  # remaining quantity
        assert request.metadata["action"] == "CANCEL"

    def test_broker_adapter_map_status(self):
        """Test mapping broker status to OMS status."""
        gateway = PaperTradingGateway()
        adapter = BrokerAdapter(gateway=gateway)

        assert adapter.map_broker_status("NEW") == OrderStatus.SUBMITTED
        assert adapter.map_broker_status("PARTIALLY_FILLED") == OrderStatus.PARTIALLY_FILLED
        assert adapter.map_broker_status("FILLED") == OrderStatus.FILLED
        assert adapter.map_broker_status("CANCELLED") == OrderStatus.CANCELLED
        assert adapter.map_broker_status("REJECTED") == OrderStatus.REJECTED
        assert adapter.map_broker_status("UNKNOWN") == OrderStatus.REJECTED
