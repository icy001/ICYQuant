"""Tests for the portfolio VaR / Expected Shortfall engine
(Commit 36 Part 1.4)."""

from decimal import Decimal

from services.portfolio_risk import (
    PortfolioVaRCalculator,
    VaRMethod,
)


def test_historical_var():

    calculator = PortfolioVaRCalculator()

    returns = [
        Decimal("-0.10"),
        Decimal("-0.05"),
        Decimal("-0.03"),
        Decimal("-0.02"),
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
        Decimal("0.05"),
        Decimal("0.06"),
    ]

    result = calculator.historical_var(
        returns,
        confidence_level=Decimal("0.90"),
    )

    assert (
        result.method
        == VaRMethod.HISTORICAL
    )

    # index = int((1 - 0.90) * 10) = 1 -> second-worst return (-0.05).
    assert (
        result.var
        == Decimal("0.05")
    )


def test_expected_shortfall():

    calculator = PortfolioVaRCalculator()

    returns = [
        Decimal("-0.10"),
        Decimal("-0.05"),
        Decimal("-0.03"),
        Decimal("-0.02"),
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
        Decimal("0.05"),
        Decimal("0.06"),
    ]

    result = (
        calculator.historical_expected_shortfall(
            returns,
            confidence_level=Decimal("0.90"),
        )
    )

    assert (
        result.expected_shortfall
        == Decimal("0.10")
    )


def test_parametric_var():

    calculator = PortfolioVaRCalculator()

    returns = [
        Decimal("-0.02"),
        Decimal("-0.01"),
        Decimal("0.00"),
        Decimal("0.01"),
        Decimal("0.02"),
    ]

    result = calculator.parametric_var(
        returns,
        confidence_level=Decimal("0.95"),
    )

    assert (
        result.var
        > Decimal("0")
    )


def test_tail_risk():

    calculator = PortfolioVaRCalculator()

    returns = [
        Decimal("-0.08"),
        Decimal("-0.05"),
        Decimal("-0.03"),
        Decimal("-0.01"),
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
        Decimal("0.05"),
        Decimal("0.06"),
    ]

    result = calculator.calculate_tail_risk(
        portfolio_id="portfolio-001",
        returns=returns,
        confidence_level=Decimal("0.90"),
    )

    assert (
        result.portfolio_id
        == "portfolio-001"
    )

    assert (
        result.expected_shortfall
        .expected_shortfall
        >= result.var.var
    )
