import pytest

from uuid import UUID

from sqlalchemy import (
    Integer,
)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from services.database import (
    Base,
    Repository,
)


class MockModel(
    Base,
):
    __tablename__ = "mock"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )


@pytest.mark.asyncio
async def test_repository_create():
    session = AsyncSession

    repo = Repository(
        session,
        MockModel,
    )

    assert repo.model is MockModel


def test_repository_init():
    repo = Repository(
        None,
        MockModel,
    )

    assert (
        repo.model
        ==
        MockModel
    )