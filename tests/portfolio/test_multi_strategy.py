from decimal import Decimal

from services.portfolio import (
    StrategyPortfolio,
    StrategyExposureAggregator,
    MasterPortfolio,
    StrategyAllocation,
    StrategyRegistry,
    MultiStrategyPortfolioEngine,
    MultiStrategyService,
)


def test_strategy_aggregation():
    aggregator = StrategyExposureAggregator()

    strategies = [
        StrategyPortfolio(
            strategy_id="alpha",
            allocated_capital=Decimal("100000"),
            current_value=Decimal("120000"),
        ),
        StrategyPortfolio(
            strategy_id="cta",
            allocated_capital=Decimal("50000"),
            current_value=Decimal("55000"),
        ),
    ]

    result = aggregator.aggregate(strategies)

    assert result == Decimal("175000")


def test_master_portfolio():
    master = MasterPortfolio()

    strategy = StrategyPortfolio(
        strategy_id="alpha",
        allocated_capital=Decimal("100000"),
        current_value=Decimal("120000"),
    )

    master.add_strategy(strategy)

    retrieved = master.get_strategy("alpha")

    assert retrieved is not None
    assert retrieved.strategy_id == "alpha"


def test_strategy_allocation():
    allocation = StrategyAllocation(
        strategy_id="alpha",
        weight=Decimal("0.5"),
    )

    assert allocation.strategy_id == "alpha"
    assert allocation.weight == Decimal("0.5")


def test_strategy_registry():
    registry = StrategyRegistry()

    strategy = StrategyPortfolio(
        strategy_id="alpha",
        allocated_capital=Decimal("100000"),
        current_value=Decimal("120000"),
    )

    registry.register(strategy)

    all_strategies = registry.list_all()

    assert len(all_strategies) == 1
    assert all_strategies[0].strategy_id == "alpha"


def test_multi_strategy_engine():
    aggregator = StrategyExposureAggregator()
    engine = MultiStrategyPortfolioEngine(aggregator)

    strategies = [
        StrategyPortfolio(
            strategy_id="alpha",
            allocated_capital=Decimal("100000"),
            current_value=Decimal("120000"),
        ),
        StrategyPortfolio(
            strategy_id="cta",
            allocated_capital=Decimal("50000"),
            current_value=Decimal("55000"),
        ),
    ]

    total = engine.calculate_value(strategies)

    assert total == Decimal("175000")


def test_multi_strategy_service():
    aggregator = StrategyExposureAggregator()
    engine = MultiStrategyPortfolioEngine(aggregator)
    service = MultiStrategyService(engine)

    strategies = [
        StrategyPortfolio(
            strategy_id="alpha",
            allocated_capital=Decimal("100000"),
            current_value=Decimal("120000"),
        ),
    ]

    total = service.valuation(strategies)

    assert total == Decimal("120000")


def test_strategy_portfolio():
    strategy = StrategyPortfolio(
        strategy_id="alpha",
        allocated_capital=Decimal("100000"),
        current_value=Decimal("120000"),
    )

    assert strategy.strategy_id == "alpha"
    assert strategy.allocated_capital == Decimal("100000")
    assert strategy.current_value == Decimal("120000")