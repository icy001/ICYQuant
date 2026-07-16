from decimal import Decimal

from services.risk import (
    RiskContext,
    RiskRequest,
)
from services.risk.account import (
    AccountRiskInfo,
)
from services.risk.rules.margin_rule import (
    MarginRule,
)


def test_margin_rule():
    context = RiskContext(
        account_id="ACC001",
        symbol="BTC",
        current_position=Decimal("0"),
        account=AccountRiskInfo(
            account_id="ACC001",
            equity=Decimal("1000"),
            used_margin=Decimal("900"),
        ),
    )

    request = RiskRequest(
        account_id="ACC001",
        symbol="BTC",
        quantity=Decimal("11"),
        price=Decimal("100"),
    )

    result = MarginRule(
        Decimal("0.1")
    ).evaluate(
        request,
        context,
    )

    assert result is not None
    assert result.reason == (
        "Insufficient margin"
    )


def test_margin_rule_approved():
    context = RiskContext(
        account_id="ACC001",
        symbol="BTC",
        current_position=Decimal("0"),
        account=AccountRiskInfo(
            account_id="ACC001",
            equity=Decimal("10000"),
            used_margin=Decimal("1000"),
        ),
    )

    request = RiskRequest(
        account_id="ACC001",
        symbol="BTC",
        quantity=Decimal("10"),
        price=Decimal("100"),
    )

    result = MarginRule(
        Decimal("0.1")
    ).evaluate(
        request,
        context,
    )

    assert result is None