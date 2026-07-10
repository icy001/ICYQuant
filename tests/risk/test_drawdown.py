import pytest

from services.risk.drawdown import MaxDrawdownRule
from services.risk.context import RiskContext
from services.risk.result import RiskDecision
from research.execution.order import Order, Side, OrderType
from research.portfolio.portfolio import Portfolio


class TestMaxDrawdownRule:

    def test_drawdown_within_limit(self):
        rule = MaxDrawdownRule(max_drawdown=0.10)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=95000.0)
        portfolio.max_equity = 100000.0

        context = RiskContext(
            portfolio=portfolio,
            account_equity=95000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.PASS

    def test_drawdown_exceeds_limit(self):
        rule = MaxDrawdownRule(max_drawdown=0.10)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=88000.0)
        portfolio.max_equity = 100000.0

        context = RiskContext(
            portfolio=portfolio,
            account_equity=88000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.REJECT
        assert "Drawdown" in result.message

    def test_drawdown_at_limit(self):
        rule = MaxDrawdownRule(max_drawdown=0.10)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=90000.0)
        portfolio.max_equity = 100000.0

        context = RiskContext(
            portfolio=portfolio,
            account_equity=90000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.REJECT

    def test_drawdown_no_max_equity(self):
        rule = MaxDrawdownRule(max_drawdown=0.10)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=100000.0)

        context = RiskContext(
            portfolio=portfolio,
            account_equity=100000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.PASS