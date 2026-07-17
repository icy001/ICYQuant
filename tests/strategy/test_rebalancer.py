from decimal import Decimal

from services.strategy.portfolio import (
    DriftDetector,
    PortfolioMonitor,
    TransactionCostEstimator,
    PortfolioRebalancer,
)


def test_weight_drift():
    detector = DriftDetector()

    drift = detector.calculate(
        current_weight=Decimal("0.3"),
        target_weight=Decimal("0.5"),
    )

    assert drift == Decimal("0.2")

    assert detector.should_rebalance(
        drift,
        Decimal("0.05"),
    )


def test_no_rebalance_needed():
    detector = DriftDetector()

    drift = detector.calculate(
        current_weight=Decimal("0.48"),
        target_weight=Decimal("0.50"),
    )

    assert not detector.should_rebalance(
        drift,
        Decimal("0.05"),
    )


def test_portfolio_monitor():
    monitor = PortfolioMonitor()

    weight = monitor.get_weight(
        value=Decimal("30000"),
        equity=Decimal("100000"),
    )

    assert weight == Decimal("0.3")


def test_transaction_cost():
    estimator = TransactionCostEstimator()

    cost = estimator.estimate(
        trade_value=Decimal("10000"),
        rate=Decimal("0.001"),
    )

    assert cost == Decimal("10")


def test_rebalance_plan():
    rebalancer = PortfolioRebalancer()

    plan = rebalancer.create_plan(
        symbol="NVDA",
        drift=Decimal("0.1"),
        price=Decimal("200"),
        cost=Decimal("10"),
    )

    assert plan.action == "BUY"
    assert plan.symbol == "NVDA"