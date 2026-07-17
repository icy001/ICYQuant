"""
Market data ingestion pipeline.
"""

from __future__ import annotations


class MarketDataIngestion:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    async def ingest(
        self,
        data,
    ):
        await self.repository.save(data)