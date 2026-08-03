"""Batch span processor."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, List, Optional


class BatchProcessor:
    """
    Batch span processor.

    Buffers spans and flushes them in batches
    for efficient export.

    Features:
    - Configurable batch size
    - Configurable flush interval
    - Manual flush support
    - Graceful shutdown flush
    - Overflow protection

    Usage:
        processor = BatchProcessor(export_fn=export_manager.export)
        processor.start()
        processor.add(span)
        await processor.flush()
        await processor.shutdown()
    """

    def __init__(
        self,
        export_fn: Optional[Callable] = None,
        batch_size: int = 512,
        flush_interval: float = 5.0,
        max_queue_size: int = 2048,
    ) -> None:
        self._export_fn = export_fn
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_queue_size = max_queue_size
        self._queue: List[Any] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._dropped: int = 0
        self._flushed: int = 0

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def dropped_count(self) -> int:
        return self._dropped

    def add(self, span: Any) -> bool:
        """Add a span to the batch queue. Returns False if dropped."""
        if len(self._queue) >= self._max_queue_size:
            self._dropped += 1
            return False
        self._queue.append(span)
        if len(self._queue) >= self._batch_size:
            asyncio.ensure_future(self._do_flush())
        return True

    async def start(self) -> None:
        """Start the background flush loop."""
        self._running = True
        self._flush_task = asyncio.ensure_future(self._flush_loop())

    async def _flush_loop(self) -> None:
        """Background flush loop."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._do_flush()

    async def _do_flush(self) -> None:
        """Flush current batch to exporter."""
        if not self._queue:
            return
        batch = self._queue[: self._batch_size]
        self._queue = self._queue[self._batch_size :]
        if self._export_fn:
            try:
                await self._export_fn(batch)
                self._flushed += len(batch)
            except Exception:
                self._queue[:0] = batch

    async def flush(self) -> None:
        """Manually flush all queued spans."""
        await self._do_flush()

    async def shutdown(self) -> None:
        """Graceful shutdown: flush remaining spans."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._do_flush()

    def get_stats(self) -> dict:
        return {
            "queue_size": self.queue_size,
            "batch_size": self._batch_size,
            "max_queue_size": self._max_queue_size,
            "flushed": self._flushed,
            "dropped": self._dropped,
            "running": self._running,
        }
