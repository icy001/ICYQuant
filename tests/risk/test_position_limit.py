from decimal import Decimal

from services.risk import (
    AccountRiskInfo,
    RiskContext,
    RiskRequest,
)
from services.risk.rules.position_limit import (
    PositionLimitRule,
)


def test_position_limit():
    context = RiskContext(
        account_id="ACC",
        symbol="AAPL",
        current_position=Decimal("80"),
        account=AccountRiskInfo(
            account_id="ACC",
            equity=Decimal("10000"),
            used_margin=Decimal("0"),
        ),
    )

    request = RiskRequest(
        account_id="ACC",
        symbol="AAPL",
        quantity=Decimal("30"),
        price=Decimal("10"),
    )

    result = PositionLimitRule(
        Decimal("100")
    ).evaluate(
        request,
        context,
    )

    assert result is not None
    assert result.reason == "Position limit exceeded"


def test_position_limit_approved():
    context = RiskContext(
        account_id="ACC",
        symbol="AAPL",
        current_position=Decimal("80"),
        account=AccountRiskInfo(
            account_id="ACC",
            equity=Decimal("10000"),
            used_margin=Decimal("0"),
        ),
    )

    request = RiskRequest(
        account_id="ACC",
        symbol="AAPL",
        quantity=Decimal("10"),
        price=Decimal("10"),
    )

    result = PositionLimitRule(
        Decimal("100")
    ).evaluate(
        request,
        context,
    )

    assert result is None