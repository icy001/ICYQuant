"""
Database configuration.

Production PostgreSQL configuration with
connection pooling, timeouts, and SSL support.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """
    Database configuration.

    Encapsulates all PostgreSQL connection
    parameters with sensible production defaults.
    """

    host: str

    port: int = 5432

    database: str

    username: str

    password: str

    echo: bool = False

    pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of persistent connections",
    )

    max_overflow: int = Field(
        default=10,
        ge=0,
        le=200,
        description="Extra connections beyond pool_size",
    )

    pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Seconds to wait for connection",
    )

    pool_recycle: int = Field(
        default=3600,
        ge=0,
        description="Seconds to recycle connections",
    )

    connect_timeout: int = Field(
        default=10,
        ge=1,
        description="Connection establishment timeout",
    )

    application_name: str = "ICYQuant"

    statement_timeout: int = Field(
        default=30000,
        ge=1000,
        description="Query timeout in milliseconds",
    )

    ssl_mode: str = "prefer"

    pool_pre_ping: bool = Field(
        default=True,
        description="Test connections before use",
    )

    pool_use_lifo: bool = Field(
        default=True,
        description="LIFO pool strategy for idle connections",
    )

    pool_reset_on_return: str = Field(
        default="rollback",
        description="Action on connection return (rollback/commit/none)",
    )

    command_timeout: int = Field(
        default=30,
        ge=1,
        description="Command execution timeout in seconds",
    )

    echo_pool: bool = Field(
        default=False,
        description="Enable pool event logging",
    )

    def url(
        self,
    ) -> str:
        """
        Build asyncpg connection URL.
        """

        return (
            "postgresql+asyncpg://"
            f"{self.username}:"
            f"{self.password}@"
            f"{self.host}:"
            f"{self.port}/"
            f"{self.database}"
        )