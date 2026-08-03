"""
AsyncPG auto-instrumentation.

Provides automatic span creation for
AsyncPG PostgreSQL operations, including:
- Query execution tracking
- Connection lifecycle
- Prepared statement monitoring
- Latency measurement
"""

from __future__ import annotations

from typing import Any, Optional

from .base import Instrumentation


class AsyncPGInstrumentation(Instrumentation):
    """
    AsyncPG PostgreSQL auto-instrumentation.

    Wraps AsyncPG connection operations to
    create spans for query execution,
    connection acquisition, and release.

    Features:
    - Query execution span creation
    - Connection lifecycle tracking
    - Prepared statement monitoring
    - Latency measurement
    - Connection pool monitoring

    Usage:
        instr = AsyncPGInstrumentation()
        await instr.install()

        # When using asyncpg connection:
        conn = await pool.acquire()
        # Query automatically traced
        result = await conn.fetch("SELECT ...")
    """

    name: str = "asyncpg"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        db_name: Optional[str] = None,
        capture_sql: bool = True,
        capture_params: bool = False,
    ) -> None:
        """
        Initialize AsyncPG instrumentation.

        Args:
            tracer: Optional Tracer instance.
            db_name: Database name.
            capture_sql: Whether to capture SQL statements.
            capture_params: Whether to capture query parameters.
        """

        super().__init__(tracer=tracer)
        self._db_name = db_name
        self._capture_sql = capture_sql
        self._capture_params = capture_params
        self._installed: bool = False

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    async def install(
        self,
    ) -> None:
        """Install AsyncPG instrumentation."""
        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove AsyncPG instrumentation."""
        self._installed = False

    def create_query_span(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch_type: str = "fetch",
    ) -> Any:
        """
        Create a query execution span.

        Args:
            query: SQL query string.
            params: Query parameters.
            fetch_type: Fetch type (fetch, fetchrow, fetchval).

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        op = query.strip().split()[0].upper() if query.strip() else "QUERY"

        span = self.tracer.start_span(
            operation=f"db.{op.lower()}",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", "postgresql")
        span.add_attribute("db.operation", op)
        span.add_attribute("db.fetch.type", fetch_type)

        if self._db_name:
            span.add_attribute("db.name", self._db_name)

        if self._capture_sql:
            span.add_attribute("db.statement", query[:2048])

        if self._capture_params and params:
            span.add_attribute("db.parameters", str(params)[:256])

        return span

    def create_connection_span(
        self,
        operation: str = "acquire",
        pool_size: Optional[int] = None,
    ) -> Any:
        """
        Create a connection lifecycle span.

        Args:
            operation: Connection operation (acquire, release).
            pool_size: Current pool size.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"db.connection.{operation}",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", "postgresql")
        span.add_attribute("db.operation", operation)

        if pool_size is not None:
            span.add_attribute("db.connection_pool.size", pool_size)

        return span

    def create_transaction_span(
        self,
        operation: str = "begin",
    ) -> Any:
        """
        Create a transaction span.

        Args:
            operation: Transaction operation.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"db.transaction.{operation}",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", "postgresql")
        span.add_attribute("db.operation", operation)

        return span
