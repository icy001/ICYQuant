import pytest
from datetime import datetime

from services.risk.engine import RiskEngine
from services.risk.context import RiskContext
from services.risk.result import RiskDecision
from services.risk.limits import PositionLimitRule
from services.risk.drawdown import MaxDrawdownRule
from services.risk.leverage import LeverageRule
from services.risk.exposure import DailyLossRule
from research.execution.order import Order, Side, OrderType
from research.portfolio.portfolio import Portfolio
from research.data.snapshot import MarketSnapshot
from research.data.bar import Bar


class TestRiskEngine:

    def test_engine_pass_all_rules(self):
        engine = RiskEngine([
            PositionLimitRule(max_weight=0.20),
            MaxDrawdownRule(max_drawdown=0.10),
            DailyLossRule(max_daily_loss=0.03),
            LeverageRule(max_gross_exposure=2.0),
        ])

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
            account_equity=100000.0,
            daily_pnl=0.0
        )

        result = engine.evaluate(order, context)

        assert result.decision == RiskDecision.PASS

    def test_engine_reject_on_drawdown(self):
        engine = RiskEngine([
            MaxDrawdownRule(max_drawdown=0.10),
        ])

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=90000.0)
        portfolio.max_equity = 100000.0

        context = RiskContext(
            portfolio=portfolio,
            account_equity=90000.0,
            daily_pnl=0.0
        )

        result = engine.evaluate(order, context)

        assert result.decision == RiskDecision.REJECT
        assert "Drawdown" in result.message

    def test_engine_modify_on_position_limit(self):
        engine = RiskEngine([
            PositionLimitRule(max_weight=0.20),
        ])

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
            account_equity=100000.0,
            daily_pnl=0.0
        )

        result = engine.evaluate(order, context)

        assert result.decision == RiskDecision.MODIFY
        assert result.modified_order is not None
        assert result.modified_order.quantity <= 200

    def test_engine_reject_on_daily_loss(self):
        engine = RiskEngine([
            DailyLossRule(max_daily_loss=0.03),
        ])

        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=97000.0)

        context = RiskContext(
            portfolio=portfolio,
            account_equity=100000.0,
            daily_pnl=-4000.0
        )

        result = engine.evaluate(order, context)

        assert result.decision == RiskDecision.REJECT
        assert "Daily loss" in result.message

    def test_engine_evaluate_all(self):
        engine = RiskEngine([
            DailyLossRule(max_daily_loss=0.03),
        ])

        order1 = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        order2 = Order(symbol="AAPL", side=Side.SELL, quantity=50, order_type=OrderType.MARKET)
        portfolio = Portfolio(initial_cash=97000.0)

        context = RiskContext(
            portfolio=portfolio,
            account_equity=100000.0,
            daily_pnl=-4000.0
        )

        results = engine.evaluate_all([order1, order2], context)

        assert len(results) == 2
        assert results[0].decision == RiskDecision.REJECT
        assert results[1].decision == RiskDecision.REJECT