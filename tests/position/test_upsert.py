from decimal import Decimal

import pytest

from services.position import (
    Position,
    PositionConflictError,
    PositionMapper,
    PositionModel,
    PositionRepository,
)


@pytest.mark.asyncio
async def test_upsert_insert(async_session):
    session = async_session

    repository = PositionRepository(session=session)

    position = Position(
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
        version=1,
    )

    await repository.upsert(position)

    result = await repository.find("ACC-001", "AAPL")

    assert result is not None
    assert result.quantity == Decimal("100")
    assert result.average_cost == Decimal("200")
    assert result.version == 1


@pytest.mark.asyncio
async def test_upsert_update(async_session):
    session = async_session

    repository = PositionRepository(session=session)

    position = Position(
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
        version=1,
    )

    await repository.upsert(position)

    existing = await repository.find("ACC-001", "AAPL")
    assert existing.version == 1

    existing.quantity = Decimal("200")
    existing.average_cost = Decimal("190")

    await repository.upsert(existing)

    updated = await repository.find("ACC-001", "AAPL")

    assert updated.quantity == Decimal("200")
    assert updated.average_cost == Decimal("190")
    assert updated.version == 2


@pytest.mark.asyncio
async def test_version_conflict(async_session):
    session = async_session

    repository = PositionRepository(session=session)

    position = Position(
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
        version=1,
    )

    await repository.upsert(position)
    await session.commit()

    updated_position = Position(
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("150"),
        average_cost=Decimal("195"),
        version=1,
    )

    await repository.upsert(updated_position)
    await session.commit()

    stale_position = Position(
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("50"),
        average_cost=Decimal("180"),
        version=1,
    )

    with pytest.raises(PositionConflictError):
        await repository.upsert(stale_position)