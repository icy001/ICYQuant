"""
Database bootstrap.

Integrates engine, session, health, and
migration management into a unified
lifecycle controller.
"""

from __future__ import annotations

from .engine import DatabaseEngine
from .health import DatabaseHealth
from .migration import MigrationManager
from .session import (
    DatabaseSession,
    UnitOfWork,
)


class DatabaseBootstrap:
    """
    Database infrastructure bootstrap.

    Coordinates lifecycle of all database
    subsystems: engine, sessions, unit of
    work, health checking, and migrations.
    """

    def __init__(
        self,
        engine: DatabaseEngine,
    ) -> None:

        self.engine: DatabaseEngine = engine

        self.sessions: DatabaseSession = (
            DatabaseSession(engine)
        )

        self.uow: UnitOfWork = UnitOfWork(
            self.sessions
        )

        self.health: DatabaseHealth = (
            DatabaseHealth(engine)
        )

        self.migrations: MigrationManager = (
            MigrationManager()
        )

    async def startup(
        self,
    ) -> None:
        """
        Start database infrastructure.

        Initializes the engine and prepares
        sessions and health checking.
        """

        await self.engine.startup()

    async def shutdown(
        self,
    ) -> None:
        """
        Stop database infrastructure.

        Releases the engine and all
        connection pool resources.
        """

        await self.engine.shutdown()