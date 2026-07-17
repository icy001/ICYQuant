from decimal import Decimal

from services.strategy.portfolio import (
    CorrelationRiskEngine,
    FactorExposureCalculator,
    ConcentrationChecker,
)


def test_high_correlation():
    engine = CorrelationRiskEngine()

    result = engine.check(
        correlation=0.9,
        threshold=0.8,
    )

    assert result.approved is False
    assert result.reason == "HIGH_CORRELATION"


def test_correlation_approved():
    engine = CorrelationRiskEngine()

    result = engine.check(
        correlation=0.7,
        threshold=0.8,
    )

    assert result.approved is True
    assert result.reason == "APPROVED"


def test_factor_exposure():
    calculator = FactorExposureCalculator()

    positions = {
        "NVDA": Decimal("100"),
        "AMD": Decimal("100"),
        "TSM": Decimal("100"),
    }

    factor_map = {
        "NVDA": "AI_SEMICONDUCTOR",
        "AMD": "AI_SEMICONDUCTOR",
        "TSM": "AI_SEMICONDUCTOR",
    }

    exposure = calculator.calculate(positions, factor_map)

    assert exposure["AI_SEMICONDUCTOR"] == Decimal("300")


def test_concentration_check():
    checker = ConcentrationChecker()

    factor_exposure = {
        "AI_SEMICONDUCTOR": Decimal("300"),
        "TECH": Decimal("200"),
    }

    result = checker.check(factor_exposure, Decimal("500"))

    assert result is True


def test_concentration_exceeded():
    checker = ConcentrationChecker()

    factor_exposure = {
        "AI_SEMICONDUCTOR": Decimal("600"),
    }

    result = checker.check(factor_exposure, Decimal("500"))

    assert result is False