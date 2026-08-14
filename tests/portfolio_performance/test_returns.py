from decimal import Decimal

import pytest

from services.portfolio_performance import (
    PortfolioReturnCalculator,
)


def test_twr_compounds_period_returns():
    calculator = PortfolioReturnCalculator()

    result = calculator.calculate_twr(
        [
            Decimal("0.10"),
            Decimal("0.20"),
        ]
    )

    assert result == Decimal("0.32")


def test_twr_with_loss():
    calculator = PortfolioReturnCalculator()

    result = calculator.calculate_twr(
        [
            Decimal("0.10"),
            Decimal("-0.10"),
        ]
    )

    assert result == Decimal("-0.01")


def test_subperiod_return_excludes_cash_flow():
    calculator = PortfolioReturnCalculator()

    result = calculator.calculate_subperiod_return(
        beginning_equity=Decimal("100000"),
        ending_equity=Decimal("115000"),
        external_cash_flow=Decimal("10000"),
    )

    assert result == Decimal("0.05")


def test_mwr_simple_case():
    calculator = PortfolioReturnCalculator()

    result = calculator.calculate_mwr(
        [
            Decimal("-100"),
            Decimal("110"),
        ]
    )

    assert abs(
        result - Decimal("0.10")
    ) < Decimal("0.0000001")


def test_mwr_requires_positive_and_negative_cash_flow():
    calculator = PortfolioReturnCalculator()

    with pytest.raises(ValueError):
        calculator.calculate_mwr(
            [
                Decimal("100"),
                Decimal("200"),
            ]
        )


def test_empty_twr_returns_zero():
    calculator = PortfolioReturnCalculator()

    assert (
        calculator.calculate_twr([])
        == Decimal("0")
    )
