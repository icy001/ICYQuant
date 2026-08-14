"""Tests for the portfolio concentration risk (Commit 36 Part 1.2)."""

from decimal import Decimal

from services.portfolio_risk import (
    ConcentrationRiskCalculator,
    ConcentrationRiskLevel,
    PositionConcentration,
)


def test_position_hhi():

    calculator = (
        ConcentrationRiskCalculator()
    )

    positions = [
        PositionConcentration(
            instrument_id="NVDA",
            weight=Decimal("0.50"),
        ),
        PositionConcentration(
            instrument_id="QQQ",
            weight=Decimal("0.30"),
        ),
        PositionConcentration(
            instrument_id="GLD",
            weight=Decimal("0.20"),
        ),
    ]

    result = (
        calculator.calculate_position_concentration(
            positions
        )
    )

    assert result.value == Decimal("0.38")

    assert (
        result.effective_number
        == Decimal("2.631578947368421052631578947")
    )

    assert (
        result.risk_level
        == ConcentrationRiskLevel.HIGH
    )


def test_largest_position():

    calculator = (
        ConcentrationRiskCalculator()
    )

    positions = [
        PositionConcentration(
            instrument_id="NVDA",
            weight=Decimal("0.40"),
        ),
        PositionConcentration(
            instrument_id="QQQ",
            weight=Decimal("0.25"),
        ),
    ]

    result = calculator.largest_position(
        positions
    )

    assert result == Decimal("0.40")


def test_top_n_concentration():

    calculator = (
        ConcentrationRiskCalculator()
    )

    positions = [
        PositionConcentration(
            instrument_id="NVDA",
            weight=Decimal("0.35"),
        ),
        PositionConcentration(
            instrument_id="AVGO",
            weight=Decimal("0.25"),
        ),
        PositionConcentration(
            instrument_id="QQQ",
            weight=Decimal("0.15"),
        ),
        PositionConcentration(
            instrument_id="GLD",
            weight=Decimal("0.10"),
        ),
    ]

    result = calculator.top_n_concentration(
        positions,
        n=2,
    )

    assert result == Decimal("0.60")


def test_sector_concentration():

    calculator = (
        ConcentrationRiskCalculator()
    )

    positions = [
        PositionConcentration(
            instrument_id="NVDA",
            weight=Decimal("0.30"),
            sector="Semiconductor",
        ),
        PositionConcentration(
            instrument_id="AVGO",
            weight=Decimal("0.20"),
            sector="Semiconductor",
        ),
        PositionConcentration(
            instrument_id="MSFT",
            weight=Decimal("0.20"),
            sector="Software",
        ),
        PositionConcentration(
            instrument_id="GLD",
            weight=Decimal("0.30"),
            sector="Commodity",
        ),
    ]

    result = (
        calculator.calculate_group_concentration(
            positions,
            group_by="sector",
        )
    )

    assert result.value == Decimal("0.38")
