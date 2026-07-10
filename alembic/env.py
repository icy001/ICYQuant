"""
Alembic environment.

Supports SQLAlchemy metadata discovery.
"""

from __future__ import annotations

from alembic import context

from sqlalchemy import (
    pool,
)

from sqlalchemy.ext.asyncio import (
    async_engine_from_config,
)

from services.database import (
    Base,
)

from services.database.config import (
    load_database_settings,
)

config = context.config

settings = load_database_settings()

config.set_main_option(
    "sqlalchemy.url",
    settings.url,
)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():

    connectable = async_engine_from_config(
        config.get_section(
            config.config_ini_section
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:

        await connection.run_sync(
            do_run_migrations
        )

    await connectable.dispose()


def do_run_migrations(connection):

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():

    import asyncio

    asyncio.run(
        run_async_migrations()
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()