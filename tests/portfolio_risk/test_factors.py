"""Tests for the portfolio factor exposure and risk attribution
(Commit 36 Part 1.3)."""

from decimal import Decimal

from services.portfolio_risk import (
    FactorRiskCalculator,
    FactorType,
    PositionFactorExposure,
)


def test_factor_exposure_aggregation():

    calculator = FactorRiskCalculator()

    exposures = [
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            factor_id="market",
            factor_type=FactorType.MARKET,
            exposure=Decimal("0.80"),
        ),
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="QQQ",
            factor_id="market",
            factor_type=FactorType.MARKET,
            exposure=Decimal("0.40"),
        ),
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            factor_id="momentum",
            factor_type=FactorType.MOMENTUM,
            exposure=Decimal("0.50"),
        ),
    ]

    result = calculator.aggregate_exposure(
        exposures
    )

    assert (
        result["market"]
        == Decimal("1.20")
    )

    assert (
        result["momentum"]
        == Decimal("0.50")
    )


def test_factor_risk_contribution():

    calculator = FactorRiskCalculator()

    exposures = [
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            factor_id="market",
            factor_type=FactorType.MARKET,
            exposure=Decimal("0.80"),
        ),
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="QQQ",
            factor_id="market",
            factor_type=FactorType.MARKET,
            exposure=Decimal("0.40"),
        ),
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="GLD",
            factor_id="commodity",
            factor_type=FactorType.COMMODITY,
            exposure=Decimal("0.80"),
        ),
    ]

    result = (
        calculator.calculate_risk_contribution(
            exposures
        )
    )

    assert (
        result.total_factor_risk
        == Decimal("2.00")
    )

    assert (
        result.factors[0].factor_id
        == "market"
    )

    assert (
        result.factors[0].contribution_pct
        == Decimal("0.60")
    )


def test_top_factor():

    calculator = FactorRiskCalculator()

    exposures = [
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            factor_id="market",
            factor_type=FactorType.MARKET,
            exposure=Decimal("0.90"),
        ),
        PositionFactorExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            factor_id="momentum",
            factor_type=FactorType.MOMENTUM,
            exposure=Decimal("0.30"),
        ),
    ]

    snapshot = (
        calculator.calculate_risk_contribution(
            exposures
        )
    )

    top_factor = calculator.top_factor(
        snapshot
    )

    assert top_factor is not None

    assert (
        top_factor.factor_id
        == "market"
    )
