"""
Database configuration.

Production database settings.
"""

from __future__ import annotations

from dataclasses import dataclass

import os


@dataclass(
    frozen=True,
)
class DatabaseSettings:
    host: str
    port: int
    username: str
    password: str
    database: str
    echo: bool

    @property
    def url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.username}:"
            f"{self.password}@"
            f"{self.host}:"
            f"{self.port}/"
            f"{self.database}"
        )


def load_database_settings(
) -> DatabaseSettings:
    return DatabaseSettings(
        host=os.getenv(
            "DB_HOST",
            "localhost",
        ),
        port=int(
            os.getenv(
                "DB_PORT",
                "5432",
            )
        ),
        username=os.getenv(
            "DB_USER",
            "icyquant",
        ),
        password=os.getenv(
            "DB_PASSWORD",
            "icyquant",
        ),
        database=os.getenv(
            "DB_NAME",
            "icyquant",
        ),
        echo=(
            os.getenv(
                "DB_ECHO",
                "false",
            )
            .lower()
            ==
            "true"
        ),
    )