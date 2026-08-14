"""Tests for the portfolio stress testing and scenario analysis
(Commit 36 Part 1.5)."""

from decimal import Decimal

from services.portfolio_risk import (
    PositionShock,
    PortfolioStressCalculator,
    ScenarioType,
    StressRiskLevel,
    StressScenario,
)


def test_stress_test():

    calculator = (
        PortfolioStressCalculator()
    )

    scenario = StressScenario(
        scenario_id="scenario-001",
        name="Market Crash",
        scenario_type=ScenarioType.HYPOTHETICAL,
        shocks=(
            PositionShock(
                instrument_id="NVDA",
                price_shock=Decimal("-0.20"),
            ),
            PositionShock(
                instrument_id="QQQ",
                price_shock=Decimal("-0.15"),
            ),
            PositionShock(
                instrument_id="GLD",
                price_shock=Decimal("-0.05"),
            ),
        ),
    )

    result = calculator.calculate(
        portfolio_id="portfolio-001",
        equity=Decimal("100000"),
        positions={
            "NVDA": Decimal("40000"),
            "QQQ": Decimal("30000"),
            "GLD": Decimal("30000"),
        },
        scenario=scenario,
    )

    assert (
        result.pnl_change
        == Decimal("-14000")
    )

    assert (
        result.stressed_equity
        == Decimal("86000")
    )

    assert (
        result.pnl_change_pct
        == Decimal("-0.14")
    )

    assert (
        result.risk_level
        == StressRiskLevel.HIGH
    )


def test_unshocked_position_is_unchanged():

    calculator = (
        PortfolioStressCalculator()
    )

    scenario = StressScenario(
        scenario_id="scenario-002",
        name="NVDA Shock",
        scenario_type=ScenarioType.HYPOTHETICAL,
        shocks=(
            PositionShock(
                instrument_id="NVDA",
                price_shock=Decimal("-0.20"),
            ),
        ),
    )

    result = calculator.calculate(
        portfolio_id="portfolio-001",
        equity=Decimal("100000"),
        positions={
            "NVDA": Decimal("50000"),
            "GLD": Decimal("50000"),
        },
        scenario=scenario,
    )

    assert (
        result.positions[1].instrument_id
        == "GLD"
    )

    assert (
        result.positions[1].pnl_change
        == Decimal("0")
    )


def test_short_position():

    calculator = (
        PortfolioStressCalculator()
    )

    scenario = StressScenario(
        scenario_id="scenario-003",
        name="Short Squeeze",
        scenario_type=ScenarioType.HYPOTHETICAL,
        shocks=(
            PositionShock(
                instrument_id="SOXS",
                price_shock=Decimal("0.20"),
            ),
        ),
    )

    result = calculator.calculate(
        portfolio_id="portfolio-001",
        equity=Decimal("100000"),
        positions={
            "SOXS": Decimal("-20000"),
        },
        scenario=scenario,
    )

    assert (
        result.pnl_change
        == Decimal("-4000")
    )


def test_scenario_matrix():

    calculator = (
        PortfolioStressCalculator()
    )

    scenarios = [
        StressScenario(
            scenario_id="scenario-001",
            name="Market Crash",
            scenario_type=ScenarioType.HISTORICAL,
            shocks=(
                PositionShock(
                    instrument_id="NVDA",
                    price_shock=Decimal("-0.20"),
                ),
                PositionShock(
                    instrument_id="QQQ",
                    price_shock=Decimal("-0.15"),
                ),
            ),
        ),
        StressScenario(
            scenario_id="scenario-002",
            name="Gold Crash",
            scenario_type=ScenarioType.HYPOTHETICAL,
            shocks=(
                PositionShock(
                    instrument_id="GLD",
                    price_shock=Decimal("-0.10"),
                ),
            ),
        ),
    ]

    results = calculator.calculate_scenarios(
        portfolio_id="portfolio-001",
        equity=Decimal("100000"),
        positions={
            "NVDA": Decimal("40000"),
            "QQQ": Decimal("30000"),
            "GLD": Decimal("30000"),
        },
        scenarios=scenarios,
    )

    assert len(results) == 2

    assert (
        results[0].pnl_change
        == Decimal("-12500")
    )

    assert (
        results[1].scenario_id
        == "scenario-002"
    )

    assert (
        results[1].pnl_change
        == Decimal("-3000")
    )
