from decimal import Decimal

from services.portfolio import (
    ReturnCalculator,
    PnLAttributionCalculator,
    StrategyAttribution,
    AlphaBetaCalculator,
    PerformanceAttributionEngine,
    PerformanceService,
    PerformanceSnapshot,
    PerformanceContribution,
    StrategyPortfolio,
)


def test_return():
    calculator = ReturnCalculator()

    result = calculator.calculate(
        Decimal("100"),
        Decimal("120"),
    )

    assert result == Decimal("0.2")


def test_return_zero_start():
    calculator = ReturnCalculator()

    result = calculator.calculate(
        Decimal("0"),
        Decimal("100"),
    )

    assert result == Decimal("0")


def test_pnl_attribution():
    calculator = PnLAttributionCalculator()

    pnl_items = {"AAPL": Decimal("100"), "MSFT": Decimal("300")}

    result = calculator.calculate(pnl_items)

    assert result["AAPL"] == Decimal("0.25")
    assert result["MSFT"] == Decimal("0.75")


def test_pnl_attribution_zero_total():
    calculator = PnLAttributionCalculator()

    pnl_items = {"AAPL": Decimal("0"), "MSFT": Decimal("0")}

    result = calculator.calculate(pnl_items)

    assert result["AAPL"] == Decimal("0")


def test_strategy_attribution():
    analyzer = StrategyAttribution()

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

    result = analyzer.analyze(strategies)

    assert "alpha" in result
    assert "cta" in result


def test_alpha_beta_calculator():
    calculator = AlphaBetaCalculator()

    alpha = calculator.calculate_alpha(
        Decimal("0.15"),
        Decimal("0.10"),
    )

    assert alpha == Decimal("0.05")


def test_beta_calculator():
    calculator = AlphaBetaCalculator()

    beta = calculator.calculate_beta(
        Decimal("0.04"),
        Decimal("0.02"),
    )

    assert beta == Decimal("2")


def test_beta_calculator_zero_variance():
    calculator = AlphaBetaCalculator()

    beta = calculator.calculate_beta(
        Decimal("0.04"),
        Decimal("0"),
    )

    assert beta == Decimal("0")


def test_performance_engine():
    analyzer = StrategyAttribution()
    pnl_calculator = PnLAttributionCalculator()
    engine = PerformanceAttributionEngine(analyzer, pnl_calculator)

    strategies = [
        StrategyPortfolio(
            strategy_id="alpha",
            allocated_capital=Decimal("100000"),
            current_value=Decimal("120000"),
        ),
    ]

    result = engine.analyze(strategies)

    assert "pnl" in result
    assert "contribution" in result


def test_performance_service():
    analyzer = StrategyAttribution()
    pnl_calculator = PnLAttributionCalculator()
    engine = PerformanceAttributionEngine(analyzer, pnl_calculator)
    service = PerformanceService(engine)

    strategies = [
        StrategyPortfolio(
            strategy_id="alpha",
            allocated_capital=Decimal("100000"),
            current_value=Decimal("120000"),
        ),
    ]

    result = service.analyze(strategies)

    assert "pnl" in result


def test_performance_snapshot():
    snapshot = PerformanceSnapshot(
        total_return=Decimal("0.15"),
        alpha=Decimal("0.05"),
        beta=Decimal("1.2"),
    )

    assert snapshot.total_return == Decimal("0.15")
    assert snapshot.alpha == Decimal("0.05")
    assert snapshot.beta == Decimal("1.2")


def test_performance_contribution():
    contribution = PerformanceContribution(
        entity_id="alpha",
        pnl=Decimal("20000"),
        contribution=Decimal("0.5"),
    )

    assert contribution.entity_id == "alpha"
    assert contribution.pnl == Decimal("20000")
    assert contribution.contribution == Decimal("0.5")