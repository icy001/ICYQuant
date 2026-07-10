import pytest
from datetime import datetime

from services.risk.limits import PositionLimitRule
from services.risk.context import RiskContext
from services.risk.result import RiskDecision
from research.execution.order import Order, Side, OrderType
from research.portfolio.portfolio import Portfolio
from research.data.snapshot import MarketSnapshot
from research.data.bar import Bar


class TestPositionLimitRule:

    def test_position_limit_within_limit(self):
        rule = PositionLimitRule(max_weight=0.20)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=100000.0)
        ts = datetime.utcnow()
        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        context = RiskContext(
            portfolio=portfolio,
            market_snapshot=snapshot,
            account_equity=100000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.PASS

    def test_position_limit_exceeds_modify(self):
        rule = PositionLimitRule(max_weight=0.20)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=300, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=100000.0)
        ts = datetime.utcnow()
        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        context = RiskContext(
            portfolio=portfolio,
            market_snapshot=snapshot,
            account_equity=100000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.MODIFY
        assert result.modified_order is not None
        assert result.modified_order.quantity == pytest.approx(200, abs=1)

    def test_position_limit_sell_order(self):
        rule = PositionLimitRule(max_weight=0.20)

        order = Order(symbol="NVDA", side=Side.SELL, quantity=-300, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=100000.0)
        ts = datetime.utcnow()
        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        context = RiskContext(
            portfolio=portfolio,
            market_snapshot=snapshot,
            account_equity=100000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.MODIFY
        assert result.modified_order is not None
        assert result.modified_order.quantity == pytest.approx(-200, abs=1)