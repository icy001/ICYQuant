"""Tests for the portfolio risk service (Commit 36 Part 1.1)."""

from datetime import date
from decimal import Decimal

from services.portfolio_risk import (
    ExposureType,
    PortfolioExposure,
    PortfolioRiskLimit,
    PortfolioRiskService,
)


def test_service_assess():

    service = PortfolioRiskService()

    exposures = [
        PortfolioExposure(
            portfolio_id="portfolio-001",
            instrument_id="NVDA",
            exposure_type=ExposureType.LONG,
            quantity=100,
            market_value=Decimal("30000"),
            weight=Decimal("0.30"),
        ),
        PortfolioExposure(
            portfolio_id="portfolio-001",
            instrument_id="QQQ",
            exposure_type=ExposureType.LONG,
            quantity=100,
            market_value=Decimal("20000"),
            weight=Decimal("0.20"),
        ),
    ]

    limits = PortfolioRiskLimit(
        portfolio_id="portfolio-001",
        max_gross_leverage=Decimal("2"),
        max_net_leverage=Decimal("2"),
        max_position_weight=Decimal("0.40"),
        max_long_exposure=Decimal("100000"),
        max_short_exposure=Decimal("50000"),
    )

    result = service.assess(
        portfolio_id="portfolio-001",
        as_of_date=date(2026, 8, 14),
        equity=Decimal("100000"),
        exposures=exposures,
        limits=limits,
    )

    assert (
        result.within_limits
        is True
    )

    assert (
        result.snapshot.gross_leverage
        == Decimal("0.50")
    )
