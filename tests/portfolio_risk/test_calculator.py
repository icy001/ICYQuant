"""Tests for the portfolio risk calculator (Commit 36 Part 1.1)."""

from datetime import date
from decimal import Decimal

from services.portfolio_risk import (
    ExposureType,
    PortfolioExposure,
    PortfolioRiskCalculator,
    PortfolioRiskLimit,
    RiskLevel,
)


def test_calculate_snapshot():

    calculator = PortfolioRiskCalculator()

    exposures = [
        PortfolioExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            exposure_type=ExposureType.LONG,
            quantity=100,
            market_value=Decimal("40000"),
            weight=Decimal("0.40"),
        ),
        PortfolioExposure(
            portfolio_id="portfolio-001",
            instrument_id="QQQ",
            exposure_type=ExposureType.LONG,
            quantity=100,
            market_value=Decimal("30000"),
            weight=Decimal("0.30"),
        ),
        PortfolioExposure(
            portfolio_id="portfolio-001",
            instrument_id="SOXS",
            exposure_type=ExposureType.SHORT,
            quantity=100,
            market_value=Decimal("10000"),
            weight=Decimal("0.10"),
        ),
    ]

    snapshot = calculator.calculate_snapshot(
        portfolio_id="portfolio-001",
        as_of_date=date(2026, 8, 14),
        equity=Decimal("100000"),
        exposures=exposures,
    )

    assert (
        snapshot.long_exposure
        == Decimal("70000")
    )

    assert (
        snapshot.short_exposure
        == Decimal("10000")
    )

    assert (
        snapshot.gross_exposure
        == Decimal("80000")
    )

    assert (
        snapshot.net_exposure
        == Decimal("60000")
    )

    assert (
        snapshot.gross_leverage
        == Decimal("0.8")
    )

    assert (
        snapshot.net_leverage
        == Decimal("0.6")
    )

    assert (
        snapshot.largest_position_weight
        == Decimal("0.40")
    )

    assert (
        snapshot.risk_level
        == RiskLevel.HIGH
    )


def test_assess_limits():

    calculator = PortfolioRiskCalculator()

    exposures = [
        PortfolioExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            exposure_type=ExposureType.LONG,
            quantity=100,
            market_value=Decimal("60000"),
            weight=Decimal("0.60"),
        ),
    ]

    snapshot = calculator.calculate_snapshot(
        portfolio_id="portfolio-001",
        as_of_date=date(2026, 8, 14),
        equity=Decimal("100000"),
        exposures=exposures,
    )

    limits = PortfolioRiskLimit(
        portfolio_id="portfolio-001",
        max_gross_leverage=Decimal("2"),
        max_net_leverage=Decimal("2"),
        max_position_weight=Decimal("0.40"),
        max_long_exposure=Decimal("100000"),
        max_short_exposure=Decimal("50000"),
    )

    assessment = calculator.assess_limits(
        snapshot,
        limits,
    )

    assert (
        assessment.within_limits
        is False
    )

    assert len(
        assessment.violations
    ) == 1

    assert (
        assessment.violations[0].metric
        == "position_weight"
    )
