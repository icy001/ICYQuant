from decimal import Decimal

import pytest

from services.portfolio import (
    RiskBudget,
    RiskSnapshot,
    RiskCalculator,
    RiskBudgetValidator,
    RiskBudgetEngine,
    RiskBudgetService,
)


def test_risk_budget():
    budget = RiskBudget(
        strategy_id="alpha",
        max_risk=Decimal("100"),
        used_risk=Decimal("20"),
    )

    validator = RiskBudgetValidator()

    assert validator.validate(budget, Decimal("50"))


def test_risk_budget_exceeded():
    budget = RiskBudget(
        strategy_id="alpha",
        max_risk=Decimal("100"),
        used_risk=Decimal("80"),
    )

    validator = RiskBudgetValidator()

    assert not validator.validate(budget, Decimal("30"))


def test_risk_calculator_remaining():
    budget = RiskBudget(
        strategy_id="alpha",
        max_risk=Decimal("100"),
        used_risk=Decimal("30"),
    )

    calculator = RiskCalculator()

    remaining = calculator.calculate_remaining(budget)

    assert remaining == Decimal("70")


def test_risk_budget_engine():
    validator = RiskBudgetValidator()
    calculator = RiskCalculator()
    engine = RiskBudgetEngine(validator, calculator)

    budget = RiskBudget(
        strategy_id="alpha",
        max_risk=Decimal("100"),
        used_risk=Decimal("20"),
    )

    result = engine.allocate(budget, Decimal("30"))

    assert result["strategy_id"] == "alpha"
    assert result["remaining"] == Decimal("50")
    assert budget.used_risk == Decimal("50")


def test_risk_budget_engine_exceeded():
    validator = RiskBudgetValidator()
    calculator = RiskCalculator()
    engine = RiskBudgetEngine(validator, calculator)

    budget = RiskBudget(
        strategy_id="alpha",
        max_risk=Decimal("100"),
        used_risk=Decimal("80"),
    )

    with pytest.raises(ValueError, match="risk budget exceeded"):
        engine.allocate(budget, Decimal("30"))


def test_risk_budget_service():
    validator = RiskBudgetValidator()
    calculator = RiskCalculator()
    engine = RiskBudgetEngine(validator, calculator)
    service = RiskBudgetService(engine)

    budget = RiskBudget(
        strategy_id="alpha",
        max_risk=Decimal("100"),
        used_risk=Decimal("0"),
    )

    result = service.allocate(budget, Decimal("40"))

    assert result["strategy_id"] == "alpha"
    assert budget.used_risk == Decimal("40")


def test_risk_snapshot():
    snapshot = RiskSnapshot(
        strategy_id="alpha",
        allocated_risk=Decimal("50"),
        remaining_risk=Decimal("50"),
    )

    assert snapshot.strategy_id == "alpha"
    assert snapshot.allocated_risk == Decimal("50")
    assert snapshot.remaining_risk == Decimal("50")