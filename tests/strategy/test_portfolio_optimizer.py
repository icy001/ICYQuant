from services.strategy.portfolio import (
    PortfolioOptimizer,
    StrategyScore,
    RebalanceController,
)


def test_strategy_allocation():
    optimizer = PortfolioOptimizer()

    result = optimizer.optimize([
        StrategyScore(
            strategy_id="A",
            sharpe=2,
            volatility=0.1,
            drawdown=0.05,
        ),
        StrategyScore(
            strategy_id="B",
            sharpe=1,
            volatility=0.2,
            drawdown=0.1,
        ),
    ])

    assert result[0].weight == 2 / 3
    assert result[1].weight == 1 / 3


def test_three_strategy_allocation():
    optimizer = PortfolioOptimizer()

    result = optimizer.optimize([
        StrategyScore(
            strategy_id="A",
            sharpe=2,
            volatility=0.1,
            drawdown=0.05,
        ),
        StrategyScore(
            strategy_id="B",
            sharpe=1,
            volatility=0.2,
            drawdown=0.1,
        ),
        StrategyScore(
            strategy_id="C",
            sharpe=1,
            volatility=0.15,
            drawdown=0.08,
        ),
    ])

    assert result[0].weight == 0.5
    assert result[1].weight == 0.25
    assert result[2].weight == 0.25


def test_rebalance_needed():
    controller = RebalanceController()

    result = controller.need_rebalance(
        current=0.25,
        target=0.40,
        threshold=0.10,
    )

    assert result is True


def test_no_rebalance_needed():
    controller = RebalanceController()

    result = controller.need_rebalance(
        current=0.38,
        target=0.40,
        threshold=0.10,
    )

    assert result is False