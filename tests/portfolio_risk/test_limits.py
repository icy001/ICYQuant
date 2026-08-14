"""Tests for the portfolio risk limit enforcement (Commit 37 Part 1.1)."""

from decimal import Decimal

from services.portfolio_risk import (
    RiskLimit,
    RiskLimitEngine,
    RiskLimitSeverity,
    RiskLimitType,
)


def test_warning_limit():

    engine = RiskLimitEngine()

    limit = RiskLimit(
        limit_id="gross-exposure-001",
        limit_type=RiskLimitType.EXPOSURE,
        metric="gross_exposure",
        warning_threshold=Decimal("1.50"),
        threshold=Decimal("1.80"),
        hard_limit=Decimal("2.00"),
    )

    result = engine.evaluate(
        metrics={
            "gross_exposure": Decimal("1.60"),
        },
        limits=[limit],
    )

    assert not result.passed

    assert (
        result.violations[0].severity
        == RiskLimitSeverity.WARNING
    )


def test_breach_limit():

    engine = RiskLimitEngine()

    limit = RiskLimit(
        limit_id="gross-exposure-001",
        limit_type=RiskLimitType.EXPOSURE,
        metric="gross_exposure",
        warning_threshold=Decimal("1.50"),
        threshold=Decimal("1.80"),
        hard_limit=Decimal("2.00"),
    )

    result = engine.evaluate(
        metrics={
            "gross_exposure": Decimal("1.90"),
        },
        limits=[limit],
    )

    assert (
        result.violations[0].severity
        == RiskLimitSeverity.BREACH
    )


def test_critical_limit():

    engine = RiskLimitEngine()

    limit = RiskLimit(
        limit_id="gross-exposure-001",
        limit_type=RiskLimitType.EXPOSURE,
        metric="gross_exposure",
        warning_threshold=Decimal("1.50"),
        threshold=Decimal("1.80"),
        hard_limit=Decimal("2.00"),
    )

    result = engine.evaluate(
        metrics={
            "gross_exposure": Decimal("2.10"),
        },
        limits=[limit],
    )

    assert (
        result.violations[0].severity
        == RiskLimitSeverity.CRITICAL
    )


def test_disabled_limit_is_ignored():

    engine = RiskLimitEngine()

    limit = RiskLimit(
        limit_id="gross-exposure-001",
        limit_type=RiskLimitType.EXPOSURE,
        metric="gross_exposure",
        warning_threshold=Decimal("1.50"),
        threshold=Decimal("1.80"),
        hard_limit=Decimal("2.00"),
        enabled=False,
    )

    result = engine.evaluate(
        metrics={
            "gross_exposure": Decimal("2.50"),
        },
        limits=[limit],
    )

    assert result.passed
    assert result.checked_limits == 0
