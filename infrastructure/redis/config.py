"""
Redis configuration.

Production Redis configuration with
connection pooling, timeouts, and auth support.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RedisConfig(BaseModel):
    """
    Redis configuration.

    Encapsulates all Redis connection
    parameters with sensible production defaults.
    """

    host: str

    port: int = Field(
        default=6379,
        ge=1,
        le=65535,
    )

    database: int = Field(
        default=0,
        ge=0,
        le=15,
    )

    username: Optional[str] = None

    password: Optional[str] = None

    ssl: bool = False

    decode_responses: bool = False

    max_connections: int = Field(
        default=100,
        ge=1,
        description="Maximum concurrent connections",
    )

    socket_timeout: int = Field(
        default=5,
        ge=1,
        description="Socket operation timeout in seconds",
    )

    socket_connect_timeout: int = Field(
        default=5,
        ge=1,
        description="Socket connection timeout in seconds",
    )

    health_check_interval: int = Field(
        default=30,
        ge=1,
        description="Health check interval in seconds",
    )

    retry_on_timeout: bool = True

    client_name: str = "ICYQuant"

    max_idle_connections: int = Field(
        default=20,
        ge=1,
        description="Maximum idle connections in pool",
    )

    socket_keepalive: bool = Field(
        default=True,
        description="Enable TCP keepalive",
    )

    retry_backoff_seconds: float = Field(
        default=0.5,
        ge=0.0,
        description="Backoff between retry attempts",
    )

    max_retry_attempts: int = Field(
        default=3,
        ge=0,
        description="Maximum connection retry attempts",
    )

    def url(
        self,
    ) -> str:
        """
        Build Redis connection URL.
        """

        protocol = (
            "rediss"
            if self.ssl
            else "redis"
        )

        auth = ""

        if self.username:
            auth += self.username

            if self.password:
                auth += (
                    f":{self.password}"
                )

            auth += "@"

        elif self.password:
            auth = (
                f":{self.password}@"
            )

        return (
            f"{protocol}://"
            f"{auth}"
            f"{self.host}:"
            f"{self.port}/"
            f"{self.database}"
        )