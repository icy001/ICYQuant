"""
SQLAlchemy Async Engine.

Production-grade async database engine
with connection pooling, event listeners,
and runtime statistics.
"""

from __future__ import annotations

from time import perf_counter

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import DatabaseConfig
from .exceptions import (
    DatabaseConnectionError,
)


class DatabaseEngine:
    """
    SQLAlchemy async engine wrapper.

    Provides lifecycle management, connection
    pool configuration, and runtime statistics
    for the database engine.
    """

    def __init__(
        self,
        config: DatabaseConfig,
    ) -> None:

        self._config = config

        self._engine: AsyncEngine | None = None

        self._session_factory: (
            async_sessionmaker[AsyncSession]
            | None
        ) = None

        self._created_at: float | None = None

    @property
    def engine(
        self,
    ) -> AsyncEngine:
        """
        Return the async engine.

        Raises DatabaseConnectionError if the
        engine has not been initialized.
        """

        if self._engine is None:
            raise DatabaseConnectionError(
                "Database engine has not been initialized. "
                "Call startup() first."
            )

        return self._engine

    @property
    def session_factory(
        self,
    ) -> async_sessionmaker[AsyncSession]:
        """
        Return the async session factory.

        Raises DatabaseConnectionError if the
        engine has not been initialized.
        """

        if self._session_factory is None:
            raise DatabaseConnectionError(
                "Session factory has not been initialized. "
                "Call startup() first."
            )

        return self._session_factory

    async def startup(
        self,
    ) -> None:
        """
        Create and configure async engine.

        Initializes the SQLAlchemy async engine
        with production-grade connection pooling
        parameters and registers event listeners.
        """

        self._engine = create_async_engine(

            self._config.url(),

            echo=self._config.echo,

            echo_pool=self._config.echo_pool,

            pool_size=self._config.pool_size,

            max_overflow=self._config.max_overflow,

            pool_timeout=self._config.pool_timeout,

            pool_recycle=self._config.pool_recycle,

            pool_pre_ping=self._config.pool_pre_ping,

            pool_use_lifo=self._config.pool_use_lifo,

            pool_reset_on_return=(
                self._config.pool_reset_on_return
            ),

            connect_args={
                "server_settings": {
                    "application_name": (
                        self._config.application_name
                    ),
                    "statement_timeout": str(
                        self._config.statement_timeout
                    ),
                },
                "command_timeout": (
                    self._config.command_timeout
                ),
            },
        )

        self._register_pool_events()

        self._session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
            autocommit=False,
        )

        self._created_at = perf_counter()

    async def shutdown(
        self,
    ) -> None:
        """
        Dispose engine and release all connections.

        Gracefully shuts down the engine, waiting
        for all checked-out connections to return.
        """

        if self._engine is None:
            return

        await self._engine.dispose()

        self._engine = None

        self._session_factory = None

        self._created_at = None

    def _register_pool_events(
        self,
    ) -> None:
        """
        Register SQLAlchemy pool event listeners.

        Tracks connection lifecycle events for
        observability and debugging.
        """

        sync_engine = self.engine.sync_engine

        @event.listens_for(
            sync_engine,
            "connect",
        )
        def on_connect(
            dbapi_connection,
            connection_record,
        ):
            connection_record.info[
                "connected"
            ] = perf_counter()

        @event.listens_for(
            sync_engine,
            "checkout",
        )
        def on_checkout(
            dbapi_connection,
            connection_record,
            connection_proxy,
        ):
            connection_record.info[
                "checkout"
            ] = perf_counter()

        @event.listens_for(
            sync_engine,
            "checkin",
        )
        def on_checkin(
            dbapi_connection,
            connection_record,
        ):
            connection_record.info[
                "checkin"
            ] = perf_counter()

    def statistics(
        self,
    ) -> dict[str, object]:
        """
        Engine runtime statistics.

        Returns configuration and runtime
        information for monitoring systems.
        """

        return {
            "initialized": (
                self._engine is not None
            ),
            "pool_size": (
                self._config.pool_size
            ),
            "max_overflow": (
                self._config.max_overflow
            ),
            "pool_pre_ping": (
                self._config.pool_pre_ping
            ),
            "pool_use_lifo": (
                self._config.pool_use_lifo
            ),
            "echo": self._config.echo,
            "echo_pool": self._config.echo_pool,
            "uptime_seconds": (
                None
                if self._created_at is None
                else round(
                    perf_counter()
                    - self._created_at,
                    3,
                )
            ),
        }

    async def ping(
        self,
    ) -> float:
        """
        Execute SELECT 1 to verify connectivity.

        Returns:
            Database latency in milliseconds.
        """

        start = perf_counter()

        async with (
            self.session_factory()
        ) as session:

            await session.execute(
                text("SELECT 1")
            )

        return (
            perf_counter() - start
        ) * 1000

    def pool_statistics(
        self,
    ) -> dict[str, int]:
        """
        Return connection pool statistics.

        Provides real-time pool metrics for
        monitoring and alerting systems.
        """

        pool = self.engine.sync_engine.pool

        return {
            "size": pool.size(),
            "checked_in": (
                pool.checkedin()
            ),
            "checked_out": (
                pool.checkedout()
            ),
            "overflow": (
                pool.overflow()
            ),
        }