from decimal import Decimal

import pytest

from services.risk import (
    AccountRiskInfo,
    PreTradeRiskService,
    RiskRejectedError,
)
from services.risk.providers import AccountProvider


class MockAccountProvider(AccountProvider):
    async def get_account_risk_info(self, account_id: str) -> AccountRiskInfo:
        return AccountRiskInfo(
            account_id=account_id,
            equity=Decimal("100000"),
            used_margin=Decimal("0"),
        )


class Order:
    account_id = "ACC001"
    symbol = "AAPL"
    quantity = Decimal("100")
    price = Decimal("10")


@pytest.mark.asyncio
async def test_service():
    service = PreTradeRiskService(
        account_provider=MockAccountProvider(),
    )
    result = await service.evaluate(Order())
    assert result.decision.value == "APPROVE"


@pytest.mark.asyncio
async def test_service_rejects_excessive_order():
    class LargeOrder:
        account_id = "ACC001"
        symbol = "AAPL"
        quantity = Decimal("200000")
        price = Decimal("10")

    service = PreTradeRiskService(
        account_provider=MockAccountProvider(),
    )
    with pytest.raises(RiskRejectedError):
        await service.evaluate(LargeOrder())


@pytest.mark.asyncio
async def test_service_insufficient_margin():
    class LowMarginProvider(AccountProvider):
        async def get_account_risk_info(self, account_id: str) -> AccountRiskInfo:
            return AccountRiskInfo(
                account_id=account_id,
                equity=Decimal("100"),
                used_margin=Decimal("90"),
            )

    class MarginOrder:
        account_id = "ACC001"
        symbol = "BTC"
        quantity = Decimal("100")
        price = Decimal("10")

    service = PreTradeRiskService(
        account_provider=LowMarginProvider(),
    )
    with pytest.raises(RiskRejectedError, match="Insufficient margin"):
        await service.evaluate(MarginOrder())