"""Tests for the portfolio risk domain models (Commit 36 Part 1.1)."""

from decimal import Decimal

from services.portfolio_risk import (
    ExposureType,
    PortfolioExposure,
)


def test_portfolio_exposure():

    exposure = PortfolioExposure(
        portfolio_id="portfolio-001",
        instrument_id="NVDA",
        exposure_type=ExposureType.LONG,
        quantity=Decimal("100"),
        market_value=Decimal("10000"),
        weight=Decimal("0.10"),
    )

    assert (
        exposure.instrument_id
        == "NVDA"
    )

    assert (
        exposure.exposure_type
        == ExposureType.LONG
    )
