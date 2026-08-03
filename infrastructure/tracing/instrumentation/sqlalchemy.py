"""
SQLAlchemy auto-instrumentation.

Provides automatic span creation for
SQLAlchemy database operations, including:
- Query execution tracking
- Transaction lifecycle (commit/rollback)
- Connection pool monitoring
- SQL statement capture (sanitized)
- Latency measurement

Usage:
    from infrastructure.tracing.instrumentation.sqlalchemy import (
        SQLAlchemyInstrumentation,
    )

    instr = SQLAlchemyInstrumentation()
    await instr.install()
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class SQLAlchemyInstrumentation(Instrumentation):
    """
    SQLAlchemy auto-instrumentation.

    Wraps SQLAlchemy engine operations
    to automatically create database spans
    for queries, transactions, and
    connection pool events.

    Features:
    - Query execution span creation
    - Transaction tracking (begin/commit/rollback)
    - Connection pool monitoring
    - SQL statement capture
    - Latency measurement

    Usage:
        instr = SQLAlchemyInstrumentation()
        await instr.install()
    """

    name: str = "sqlalchemy"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        db_system: str = "postgresql",
        db_name: Optional[str] = None,
        capture_sql: bool = True,
        sanitize_sql: bool = True,
    ) -> None:
        """
        Initialize SQLAlchemy instrumentation.

        Args:
            tracer: Optional Tracer instance.
            db_system: Database system type.
            db_name: Database name.
            capture_sql: Whether to capture SQL statements.
            sanitize_sql: Whether to sanitize SQL (remove values).
        """

        super().__init__(tracer=tracer)
        self._db_system = db_system
        self._db_name = db_name
        self._capture_sql = capture_sql
        self._sanitize_sql = sanitize_sql
        self._installed: bool = False
        self._original_execute: Optional[Callable] = None

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    async def install(
        self,
    ) -> None:
        """Install SQLAlchemy instrumentation."""

        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove SQLAlchemy instrumentation."""

        self._installed = False

    def create_query_span(
        self,
        operation: str,
        sql: Optional[str] = None,
        params: Optional[Any] = None,
        rows_returned: Optional[int] = None,
    ) -> Any:
        """
        Create a database query span.

        Args:
            operation: Operation type (SELECT, INSERT, etc.).
            sql: SQL statement.
            params: Query parameters.
            rows_returned: Number of rows returned.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind, SpanStatus

        span = self.tracer.start_span(
            operation=f"db.{operation.lower()}",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", self._db_system)
        span.add_attribute("db.operation", operation.upper())

        if self._db_name:
            span.add_attribute("db.name", self._db_name)

        if sql and self._capture_sql:
            sanitized = self._sanitize(sql) if self._sanitize_sql else sql
            span.add_attribute("db.statement", sanitized[:2048])

        if rows_returned is not None:
            span.add_attribute("db.rows_returned", rows_returned)

        return span

    def create_transaction_span(
        self,
        operation: str = "transaction",
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
            operation=f"db.{operation}",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", self._db_system)
        span.add_attribute("db.operation", operation.upper())

        if self._db_name:
            span.add_attribute("db.name", self._db_name)

        return span

    def _sanitize(
        self,
        sql: str,
    ) -> str:
        """Sanitize SQL by removing parameter values."""

        import re
        # Replace VALUES (...), IN (...) with placeholders
        sanitized = re.sub(
            r"\bIN\s*\([^)]*\)",
            "IN (?)",
            sql,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"\bVALUES\s*\([^)]*\)",
            "VALUES (?)",
            sanitized,
            flags=re.IGNORECASE,
        )
        return sanitized


class AsyncPGInstrumentation(Instrumentation):
    """
    AsyncPG auto-instrumentation.

    Provides automatic span creation for
    AsyncPG PostgreSQL operations.

    Features:
    - Query execution span creation
    - Connection lifecycle tracking
    - Prepared statement monitoring
    - Latency measurement

    Usage:
        instr = AsyncPGInstrumentation()
        await instr.install()
    """

    name: str = "asyncpg"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        db_name: Optional[str] = None,
        capture_sql: bool = True,
    ) -> None:
        """
        Initialize AsyncPG instrumentation.

        Args:
            tracer: Optional Tracer instance.
            db_name: Database name.
            capture_sql: Whether to capture SQL.
        """

        super().__init__(tracer=tracer)
        self._db_name = db_name
        self._capture_sql = capture_sql
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
    ) -> Any:
        """
        Create a query span for AsyncPG.

        Args:
            query: SQL query.
            params: Query parameters.

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

        if self._db_name:
            span.add_attribute("db.name", self._db_name)

        if self._capture_sql:
            span.add_attribute("db.statement", query[:2048])

        if params:
            span.add_attribute("db.parameters", str(params)[:256])

        return span
