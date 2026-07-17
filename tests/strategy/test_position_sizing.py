from decimal import Decimal

from services.strategy import (
    PositionSizer,
    RiskBudget,
)


def test_position_size():
    budget = RiskBudget(
        account_equity=Decimal("100000"),
        max_risk_percent=Decimal("0.01"),
        max_position_value=Decimal("50000"),
    )

    sizer = PositionSizer()

    result = sizer.calculate(
        price=Decimal("200"),
        stop_loss_distance=Decimal("10"),
        budget=budget,
    )

    assert result.approved is True
    assert result.quantity == Decimal("100")


def test_position_size_exceeds_budget():
    budget = RiskBudget(
        account_equity=Decimal("100000"),
        max_risk_percent=Decimal("0.01"),
        max_position_value=Decimal("5000"),
    )

    sizer = PositionSizer()

    result = sizer.calculate(
        price=Decimal("200"),
        stop_loss_distance=Decimal("10"),
        budget=budget,
    )

    assert result.approved is False
    assert result.quantity == Decimal("0")