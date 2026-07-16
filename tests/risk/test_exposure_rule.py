from decimal import Decimal

from services.risk import (
    AccountRiskInfo,
    RiskContext,
    RiskRequest,
)
from services.risk.rules.exposure_limit import (
    ExposureLimitRule,
)


def test_exposure_limit():
    context = RiskContext(
        account_id="ACC001",
        symbol="AAPL",
        current_position=Decimal("500"),
        account=AccountRiskInfo(
            account_id="ACC001",
            equity=Decimal("100000"),
            used_margin=Decimal("0"),
        ),
    )

    request = RiskRequest(
        account_id="ACC001",
        symbol="AAPL",
        quantity=Decimal("800"),
        price=Decimal("100"),
    )

    result = ExposureLimitRule(
        Decimal("100000"),
    ).evaluate(
        request,
        context,
    )

    assert result is not None
    assert (
        result.reason
        ==
        "Exposure limit exceeded"
    )


def test_exposure_limit_approved():
    context = RiskContext(
        account_id="ACC001",
        symbol="AAPL",
        current_position=Decimal("500"),
        account=AccountRiskInfo(
            account_id="ACC001",
            equity=Decimal("100000"),
            used_margin=Decimal("0"),
        ),
    )

    request = RiskRequest(
        account_id="ACC001",
        symbol="AAPL",
        quantity=Decimal("100"),
        price=Decimal("100"),
    )

    result = ExposureLimitRule(
        Decimal("100000"),
    ).evaluate(
        request,
        context,
    )

    assert result is None