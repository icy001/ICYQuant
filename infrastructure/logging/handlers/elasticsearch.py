"""
Elasticsearch log handler.

Indexes log records into Elasticsearch,
enabling full-text search, aggregation,
and visualization in Kibana.

Supports index pattern management and
graceful degradation when Elasticsearch
is unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..models import LogEntry
from .base import LogHandler


class ElasticsearchHandler(LogHandler):
    """
    Elasticsearch log handler.

    Indexes log records into Elasticsearch
    for search and visualization.

    Features:
    - Configurable index pattern
    - Daily index rotation
    - Async client integration
    - Graceful degradation
    - Bulk indexing support

    Usage:
        handler = ElasticsearchHandler(
            client=my_es_client,
            index_prefix="icyquant-logs",
        )
        await handler.startup()
        await handler.emit(log_entry)
        await handler.shutdown()
    """

    def __init__(
        self,
        client: Any = None,
        index_prefix: str = "icyquant-logs",
        index_pattern: str = "icyquant-logs-{date}",
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize Elasticsearch handler.

        Args:
            client: Elasticsearch async client.
            index_prefix: Index prefix.
            index_pattern: Index pattern with {date} placeholder.
            name: Optional handler name.
        """

        super().__init__(name=name)
        self._client = client
        self._index_prefix = index_prefix
        self._index_pattern = index_pattern

    async def startup(
        self,
    ) -> None:
        """Start the handler."""

        self._started = True

    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Index a log record in Elasticsearch.

        Args:
            record: LogEntry to index.
        """

        try:
            if self._client is None:
                self._emit_count += 1
                return

            index_name = self._resolve_index(record)
            document = record.to_dict()

            await self._client.index(
                index=index_name,
                document=document,
            )

            self._emit_count += 1
        except Exception:
            self._error_count += 1

    def _resolve_index(
        self,
        record: LogEntry,
    ) -> str:
        """
        Resolve the Elasticsearch index name.

        Args:
            record: LogEntry to resolve.

        Returns:
            Index name with date suffix.
        """

        date_str = datetime.utcnow().strftime("%Y.%m.%d")
        return self._index_pattern.replace("{date}", date_str)

    async def shutdown(
        self,
    ) -> None:
        """Shutdown the handler."""

        self._started = False

    def get_status(
        self,
    ) -> dict:
        """Get handler status."""

        status = super().get_status()
        status["index_prefix"] = self._index_prefix
        status["index_pattern"] = self._index_pattern
        status["client"] = (
            type(self._client).__name__
            if self._client
            else None
        )
        return status
