import pytest
from datetime import datetime

from services.risk.leverage import LeverageRule
from services.risk.context import RiskContext
from services.risk.result import RiskDecision
from research.execution.order import Order, Side, OrderType
from research.portfolio.portfolio import Portfolio
from research.data.snapshot import MarketSnapshot
from research.data.bar import Bar


class TestLeverageRule:

    def test_leverage_within_limit(self):
        rule = LeverageRule(max_gross_exposure=2.0)

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

    def test_leverage_exceeds_limit(self):
        rule = LeverageRule(max_gross_exposure=1.0)

        order = Order(symbol="NVDA", side=Side.BUY, quantity=1500, order_type=OrderType.MARKET)
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

        assert result.decision == RiskDecision.REJECT
        assert "Gross leverage" in result.message

    def test_leverage_with_existing_positions(self):
        rule = LeverageRule(max_gross_exposure=2.0)

        order = Order(symbol="AAPL", side=Side.BUY, quantity=500, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=100000.0)
        ts = datetime.utcnow()
        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={
                "NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000),
                "AAPL": Bar(symbol="AAPL", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)
            }
        )

        context = RiskContext(
            portfolio=portfolio,
            market_snapshot=snapshot,
            account_equity=100000.0
        )

        result = rule.evaluate(order, context)

        assert result.decision == RiskDecision.PASS