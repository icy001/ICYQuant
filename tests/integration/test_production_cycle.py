import pytest

from services.execution.gateway import ExecutionGateway
from services.ledger.repository import EventRepository
from services.ledger.service.service import LedgerService
from services.ledger.store import InMemoryEventStore
from services.oms.service import OMSService
from services.oms.state import OrderStatus
from services.portfolio.portfolio import Portfolio
from services.risk.checker import RiskChecker
from services.risk.limits import RiskLimits


class TestProductionCycle:
    def test_full_production_trade_cycle(self):
        portfolio = Portfolio(cash=100000.0)
        portfolio.market_prices["NVDA"] = 480.0

        risk_checker = RiskChecker(RiskLimits())
        gateway = ExecutionGateway()
        gateway.connect()

        oms = OMSService(risk_checker=risk_checker, execution_gateway=gateway)

        store = InMemoryEventStore()
        repo = EventRepository(store)
        ledger = LedgerService(repo)

        order = oms.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )

        assert order.status == OrderStatus.CREATED

        order = oms.submit(order.order_id, portfolio)

        assert order.status == OrderStatus.FILLED
        assert order.risk_check_result["overall"] is True

        portfolio.update_position("NVDA", 100)
        portfolio.cash -= 100 * 480.0

        assert portfolio.positions["NVDA"] == 100
        assert portfolio.cash == 100000.0 - 48000.0

        event = ledger.record_order_filled(
            user_id="default",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
        )

        assert event.event_type.value == "ORDER_FILLED"
        assert event.payload["symbol"] == "NVDA"
        assert event.payload["quantity"] == 100
        assert event.payload["price"] == 480.0
        assert event.payload["cash_change"] == -48000.0

    def test_risk_rejects_order(self):
        portfolio = Portfolio(cash=1000.0)
        portfolio.market_prices["NVDA"] = 480.0

        risk_checker = RiskChecker(RiskLimits(max_order_quantity=50))
        gateway = ExecutionGateway()

        oms = OMSService(risk_checker=risk_checker, execution_gateway=gateway)

        order = oms.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )

        order = oms.submit(order.order_id, portfolio)

        assert order.status == OrderStatus.REJECTED
        assert order.risk_check_result["overall"] is False

    def test_order_lifecycle_transitions(self):
        portfolio = Portfolio(cash=100000.0)
        portfolio.market_prices["NVDA"] = 480.0
        risk_checker = RiskChecker(RiskLimits())
        gateway = ExecutionGateway()
        gateway.connect()

        oms = OMSService(risk_checker=risk_checker, execution_gateway=gateway)

        order = oms.create_order("NVDA", "BUY", 100, 480.0)
        assert order.status == OrderStatus.CREATED

        order = oms.submit(order.order_id, portfolio)

        assert order.status == OrderStatus.FILLED

    def test_circuit_breaker_blocks_trading(self):
        limits = RiskLimits(max_drawdown=0.03)
        from services.risk.monitor import RiskMonitor

        monitor = RiskMonitor(limits)

        portfolio = Portfolio(cash=100000.0)
        account = {"cash": 100000.0}

        monitor.update(account, portfolio)

        assert monitor.allow_trade(account) is True

        portfolio.cash = 96000.0
        account = {"cash": 96000.0}
        monitor.update(account, portfolio)

        assert monitor.metrics.daily_loss == 4000.0
        assert monitor.allow_trade(account) is False