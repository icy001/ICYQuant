import pytest

from services.database import (
    DatabaseHealth,
)


class MockConnection:

    def __init__(self):
        self._entered = False

    async def execute(
        self,
        query,
    ):
        return True

    async def __aenter__(self):
        self._entered = True
        return self

    async def __aexit__(
        self,
        *args,
    ):
        pass


class MockEngine:

    def connect(self):
        return MockConnection()


@pytest.mark.asyncio
async def test_database_health():

    health = DatabaseHealth(
        MockEngine()
    )

    result = await health.check()

    assert (
        result["status"]
        ==
        "healthy"
    )