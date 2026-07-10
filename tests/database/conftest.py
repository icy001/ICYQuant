"""
Database test fixtures.
"""

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)


from services.database import (
    Base,
)


TEST_DATABASE_URL = (
    "sqlite+aiosqlite:///:memory:"
)


@pytest_asyncio.fixture
async def engine():

    engine = create_async_engine(
        TEST_DATABASE_URL,
    )

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(
    engine,
):

    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with factory() as session:

        yield session


@pytest.fixture
def session_factory(
    engine,
):

    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    return factory