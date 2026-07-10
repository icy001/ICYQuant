import pytest

from services.database import (
    TransactionManager,
)


class MockSession:

    def __init__(self):
        self.committed = False
        self.rollbacked = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rollbacked = True


class MockFactory:

    def __init__(self):
        self.session = MockSession()

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        pass


@pytest.mark.asyncio
async def test_transaction_commit():

    factory = MockFactory()

    manager = TransactionManager(
        factory
    )

    async with manager.transaction():

        pass

    assert (
        factory.session.committed
    )


@pytest.mark.asyncio
async def test_transaction_rollback():

    factory = MockFactory()

    manager = TransactionManager(
        factory
    )

    with pytest.raises(
        ValueError
    ):

        async with manager.transaction():
            raise ValueError()

    assert (
        factory.session.rollbacked
    )