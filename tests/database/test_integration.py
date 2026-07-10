"""
Database integration tests.

Validate full persistence flow.
"""

from __future__ import annotations

import pytest

from sqlalchemy import (
    Integer,
    String,
    select,
)


from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)


from services.database import (
    Base,
    Repository,
    TransactionManager,
)


from services.database.mixins import (
    UUIDMixin,
    TimestampMixin,
)


class UserModel(
    UUIDMixin,
    TimestampMixin,
    Base,
):

    __tablename__ = "test_users"

    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )


@pytest.mark.asyncio
async def test_repository_create_and_query(
    async_session,
):

    repo = Repository(
        async_session,
        UserModel,
    )

    user = UserModel(
        name="trader",
    )

    await repo.create(
        user
    )

    await async_session.commit()


    result = await async_session.execute(
        select(
            UserModel
        )
    )

    users = result.scalars().all()


    assert len(users) == 1

    assert (
        users[0].name
        ==
        "trader"
    )


@pytest.mark.asyncio
async def test_transaction_commit(
    session_factory,
):

    manager = TransactionManager(
        session_factory
    )

    async with manager.transaction() as session:

        repo = Repository(
            session,
            UserModel,
        )

        await repo.create(
            UserModel(
                name="commit_user"
            )
        )


@pytest.mark.asyncio
async def test_transaction_rollback(
    session_factory,
):

    manager = TransactionManager(
        session_factory
    )

    with pytest.raises(
        ValueError
    ):

        async with manager.transaction() as session:

            repo = Repository(
                session,
                UserModel,
            )

            await repo.create(
                UserModel(
                    name="rollback_user"
                )
            )

            raise ValueError(
                "rollback"
            )