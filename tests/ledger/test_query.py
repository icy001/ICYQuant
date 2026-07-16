import pytest

from services.ledger import (
    JournalQuery,
    LedgerQueryService,
)


class FakeRepository:
    async def list_by_reference(
        self,
        reference_type,
        reference_id,
    ):
        return ["journal-1"]

    async def search(
        self,
        query,
    ):
        return ["journal-1"]


@pytest.mark.asyncio
async def test_query_service():
    repository = FakeRepository()

    service = LedgerQueryService(
        repository
    )

    result = await service.find_by_reference(
        "TRADE",
        "trade-001",
    )

    assert result == ["journal-1"]

    result = await service.execute(
        JournalQuery(
            reference_type="TRADE",
            reference_id="trade-001",
        )
    )

    assert result == ["journal-1"]