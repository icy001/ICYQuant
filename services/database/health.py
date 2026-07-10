"""
Database health check service.
"""

from __future__ import annotations

from sqlalchemy import text

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
)


class DatabaseHealth:

    def __init__(
        self,
        engine: AsyncEngine,
    ):

        self.engine = engine

    async def check(self) -> dict:

        try:

            async with self.engine.connect() as connection:

                await connection.execute(
                    text(
                        "SELECT 1"
                    )
                )

            return {
                "status":
                "healthy",

                "database":
                "postgresql",
            }

        except Exception as exc:

            return {
                "status":
                "unhealthy",

                "error":
                str(exc),
            }

    async def is_available(self) -> bool:

        result = await self.check()

        return (
            result["status"]
            ==
            "healthy"
        )