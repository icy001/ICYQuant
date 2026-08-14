"""Tests for the portfolio risk decision engine (Commit 37 Part 1.2).

Covers the decision priority matrix:

.. code-block:: text

    CRITICAL > REJECT (BREACH) > WARNING > APPROVE
"""

from decimal import Decimal

from services.portfolio_risk import (
    PortfolioRiskDecision,
    PortfolioRiskDecisionEngine,
    RiskLimit,
    RiskLimitAssessment,
    RiskLimitEngine,
    RiskLimitSeverity,
    RiskLimitType,
)


def build_limit():
    return RiskLimit(
        limit_id="gross-exposure-001",
        limit_type=RiskLimitType.EXPOSURE,
        metric="gross_exposure",
        warning_threshold=Decimal("1.50"),
        threshold=Decimal("1.80"),
        hard_limit=Decimal("2.00"),
    )


def test_approve():

    limit_engine = RiskLimitEngine()
    decision_engine = (
        PortfolioRiskDecisionEngine()
    )

    assessment = limit_engine.evaluate(
        metrics={
            "gross_exposure": Decimal("1.20"),
        },
        limits=[build_limit()],
    )

    result = decision_engine.evaluate(
        assessment
    )

    assert (
        result.decision
        == PortfolioRiskDecision.APPROVE
    )

    assert result.warning_count == 0
    assert result.breach_count == 0
    assert result.critical_count == 0


def test_warning():

    limit_engine = RiskLimitEngine()
    decision_engine = (
        PortfolioRiskDecisionEngine()
    )

    assessment = limit_engine.evaluate(
        metrics={
            "gross_exposure": Decimal("1.60"),
        },
        limits=[build_limit()],
    )

    result = decision_engine.evaluate(
        assessment
    )

    assert (
        result.decision
        == PortfolioRiskDecision.WARNING
    )

    assert result.warning_count == 1


def test_reject():

    limit_engine = RiskLimitEngine()
    decision_engine = (
        PortfolioRiskDecisionEngine()
    )

    assessment = limit_engine.evaluate(
        metrics={
            "gross_exposure": Decimal("1.90"),
        },
        limits=[build_limit()],
    )

    result = decision_engine.evaluate(
        assessment
    )

    assert (
        result.decision
        == PortfolioRiskDecision.REJECT
    )

    assert result.breach_count == 1


def test_critical():

    limit_engine = RiskLimitEngine()
    decision_engine = (
        PortfolioRiskDecisionEngine()
    )

    assessment = limit_engine.evaluate(
        metrics={
            "gross_exposure": Decimal("2.20"),
        },
        limits=[build_limit()],
    )

    result = decision_engine.evaluate(
        assessment
    )

    assert (
        result.decision
        == PortfolioRiskDecision.CRITICAL
    )

    assert result.critical_count == 1


def test_critical_overrides_breach():

    limit_engine = RiskLimitEngine()
    decision_engine = (
        PortfolioRiskDecisionEngine()
    )

    limits = [
        RiskLimit(
            limit_id="exposure",
            limit_type=RiskLimitType.EXPOSURE,
            metric="gross_exposure",
            warning_threshold=Decimal("1.50"),
            threshold=Decimal("1.80"),
            hard_limit=Decimal("2.00"),
        ),
        RiskLimit(
            limit_id="var",
            limit_type=RiskLimitType.VAR,
            metric="var_95_1d",
            warning_threshold=Decimal("0.025"),
            threshold=Decimal("0.035"),
            hard_limit=Decimal("0.05"),
        ),
    ]

    assessment = limit_engine.evaluate(
        metrics={
            "gross_exposure": Decimal("1.90"),
            "var_95_1d": Decimal("0.08"),
        },
        limits=limits,
    )

    result = decision_engine.evaluate(
        assessment
    )

    assert (
        result.decision
        == PortfolioRiskDecision.CRITICAL
    )

    assert result.breach_count == 1
    assert result.critical_count == 1
