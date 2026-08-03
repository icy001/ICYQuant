"""
Database infrastructure.

Provides production-grade PostgreSQL
connection management with async support.
"""

from .bootstrap import DatabaseBootstrap
from .config import DatabaseConfig
from .engine import DatabaseEngine
from .migration import MigrationManager
from .session import (
    DatabaseSession,
    UnitOfWork,
    Repository,
)
from .health import (
    DatabaseHealth,
    DatabaseHealthReport,
)
from .exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseTransactionError,
    DatabaseTimeoutError,
    DatabaseHealthError,
)

__all__ = [
    "DatabaseBootstrap",
    "DatabaseConfig",
    "DatabaseEngine",
    "DatabaseSession",
    "MigrationManager",
    "UnitOfWork",
    "Repository",
    "DatabaseHealth",
    "DatabaseHealthReport",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseTransactionError",
    "DatabaseTimeoutError",
    "DatabaseHealthError",
]