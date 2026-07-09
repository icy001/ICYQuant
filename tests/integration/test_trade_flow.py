import pytest

from services.execution.service import ExecutionService
from services.oms.service import OrderService
from services.portfolio.portfolio import Portfolio
from services.risk.checker import RiskChecker
from services.risk.limits import RiskLimits


class TestTradeFlow:
    def test_full_trade_flow(self):
        portfolio = Portfolio(cash=100000.0)
        portfolio.market_prices["NVDA"] = 480.0

        risk_checker = RiskChecker(RiskLimits())

        order_service = OrderService()

        execution_service = ExecutionService()

        order = order_service.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )

        assert order.order_id is not None
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 100

        risk_result = risk_checker.check(order, portfolio)
        assert risk_result["overall"] is True

        order = order_service.submit_order(order.order_id)
        assert order.status.value == "SUBMITTED"

        order = order_service.accept_order(order.order_id)
        assert order.status.value == "ACCEPTED"

        fill = execution_service.execute_order(order)

        assert fill.order_id == order.order_id
        assert fill.symbol == "NVDA"
        assert fill.quantity == 100
        assert fill.price == 480.0

        delta = fill.quantity if order.side == "BUY" else -fill.quantity
        portfolio.update_position(fill.symbol, delta)
        portfolio.cash -= fill.quantity * fill.price

        assert portfolio.positions["NVDA"] == 100
        assert portfolio.cash == 100000.0 - (100 * 480.0)

        order = order_service.fill_order(order.order_id)
        assert order.status.value == "FILLED"

    def test_trade_flow_with_sell(self):
        portfolio = Portfolio(cash=100000.0)
        portfolio.positions["NVDA"] = 200
        portfolio.market_prices["NVDA"] = 480.0

        risk_checker = RiskChecker(RiskLimits())
        order_service = OrderService()
        execution_service = ExecutionService()

        order = order_service.create_order(
            symbol="NVDA",
            side="SELL",
            quantity=100,
            price=480.0,
        )

        risk_result = risk_checker.check(order, portfolio)
        assert risk_result["overall"] is True

        order = order_service.submit_order(order.order_id)
        order = order_service.accept_order(order.order_id)

        fill = execution_service.execute_order(order)

        delta = fill.quantity if order.side == "BUY" else -fill.quantity
        portfolio.update_position(fill.symbol, delta)
        portfolio.cash += fill.quantity * fill.price

        assert portfolio.positions["NVDA"] == 100
        assert portfolio.cash == 100000.0 + (100 * 480.0)

    def test_risk_rejects_order(self):
        portfolio = Portfolio(cash=1000.0)
        portfolio.market_prices["NVDA"] = 480.0

        risk_checker = RiskChecker(RiskLimits(max_order_quantity=50))
        order_service = OrderService()

        order = order_service.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )

        risk_result = risk_checker.check(order, portfolio)
        assert risk_result["overall"] is False
        assert risk_result["order_quantity"] is False