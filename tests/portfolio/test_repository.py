import pytest
from decimal import Decimal

from services.portfolio import (
    CashBalance,
    InMemoryPortfolioRepository,
    Portfolio,
    PortfolioRecoveryService,
    PortfolioStatus,
)


@pytest.mark.asyncio
async def test_repository_save_load():
    repo = InMemoryPortfolioRepository()

    portfolio = Portfolio(
        account_id="ACC001",
        status=PortfolioStatus.ACTIVE,
        cash=CashBalance(
            currency="USD",
            available=Decimal("1000"),
            frozen=Decimal("0"),
        ),
    )

    await repo.save(portfolio)

    recovered = await PortfolioRecoveryService(repo).recover("ACC001")

    assert recovered is not None
    assert recovered.account_id == "ACC001"


@pytest.mark.asyncio
async def test_repository_load_nonexistent():
    repo = InMemoryPortfolioRepository()

    recovered = await repo.load("ACC999")

    assert recovered is None