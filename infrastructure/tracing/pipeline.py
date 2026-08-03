"""
Trace export pipeline.

Connects the full span processing pipeline:

    Tracer
       │
       ▼
    Span Processor (Batch)
       │
       ▼
    Queue
       │
       ▼
    Compression
       │
       ▼
    Retry
       │
       ▼
    Timeout
       │
       ▼
    Export Manager
       │
       ├────► OTLP gRPC
       ├────► OTLP HTTP
       ├────► Jaeger
       ├────► Tempo
       ├────► Zipkin
       └────► Console

Failure Recovery:
    Exporter Failure
       ↓
    Retry Queue
       ↓
    Disk Buffer
       ↓
    Recovery
       ↓
    Continue Export
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, List, Optional

from .exporters import ExportManager, ExporterFactory
from .metrics import TraceMetrics
from .processor import (
    BatchProcessor,
    CompressionManager,
    RetryPolicy,
    SpanBuffer,
    SpanQueue,
    TimeoutController,
)


class TracePipeline:
    """
    Trace export pipeline.

    Orchestrates the full span processing pipeline,
    from span creation to export, including batching,
    compression, retry, timeout, and buffering.

    Features:
    - Batch processing with configurable size/interval
    - Compression (gzip/zstd/snappy)
    - Retry with exponential backoff
    - Timeout control
    - Memory + disk buffering
    - Multi-exporter support
    - Failure recovery

    Usage:
        pipeline = TracePipeline()
        await pipeline.start()
        pipeline.add_span(span)
        await pipeline.flush()
        await pipeline.shutdown()
    """

    def __init__(
        self,
        batch_size: int = 512,
        flush_interval: float = 5.0,
        max_queue_size: int = 2048,
        compression: str = "gzip",
        max_retry: int = 5,
        timeout: float = 30.0,
        disk_path: Optional[str] = None,
    ) -> None:
        """
        Initialize pipeline.

        Args:
            batch_size: Batch size for flushing.
            flush_interval: Flush interval in seconds.
            max_queue_size: Max queue size before overflow.
            compression: Compression algorithm.
            max_retry: Max retry attempts.
            timeout: Export timeout in seconds.
            disk_path: Optional disk buffer path.
        """

        self._metrics = TraceMetrics()

        self._queue = SpanQueue(max_size=max_queue_size)
        self._buffer = SpanBuffer(disk_path=disk_path)
        self._compression = CompressionManager(algorithm=compression)
        self._retry = RetryPolicy(max_retry=max_retry)
        self._timeout = TimeoutController(timeout=timeout)

        self._export_manager = ExportManager(mode="broadcast")
        self._batch_processor = BatchProcessor(
            export_fn=self._export_batch,
            batch_size=batch_size,
            flush_interval=flush_interval,
            max_queue_size=max_queue_size,
        )

        self._running: bool = False

    @property
    def metrics(self) -> TraceMetrics:
        """Get pipeline metrics."""
        return self._metrics

    @property
    def export_manager(self) -> ExportManager:
        """Get the export manager."""
        return self._export_manager

    @property
    def queue(self) -> SpanQueue:
        """Get the span queue."""
        return self._queue

    @property
    def buffer(self) -> SpanBuffer:
        """Get the span buffer."""
        return self._buffer

    def add_exporter(self, exporter: Any) -> None:
        """Register an exporter."""
        self._export_manager.register(exporter)

    def add_span(self, span: Any) -> bool:
        """Add a span to the pipeline."""
        added = self._queue.put(span)
        if not added:
            added = self._buffer.put(span)
        if added:
            self._metrics.record_span()
        else:
            self._metrics.dropped_spans += 1
        return added

    async def start(self) -> None:
        """Start the pipeline."""
        self._running = True
        await self._export_manager.startup()
        await self._batch_processor.start()

        # Recover any spans from disk buffer
        recovered = self._buffer.recover()
        for span in recovered:
            self._queue.put(span)

    async def _export_batch(self, spans: List[Any]) -> bool:
        """Export a batch of spans through the full pipeline."""
        self._metrics.export_total += 1
        start_time = datetime.utcnow()

        try:
            result = await self._timeout.execute(
                self._retry.execute,
                self._export_manager.export,
                spans,
            )

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._metrics.export_latency_ms = latency

            if result:
                self._metrics.export_success += 1
                return True
            else:
                self._metrics.export_failed += 1
                # Buffer failed spans for retry
                for span in spans:
                    self._buffer.put(span)
                return False
        except Exception:
            self._metrics.export_failed += 1
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._metrics.export_latency_ms = latency
            return False

    async def flush(self) -> None:
        """Flush all queued spans."""
        batch = self._queue.drain()
        if batch:
            await self._export_batch(batch)
        await self._export_manager.flush()

    async def shutdown(self) -> None:
        """Graceful shutdown: flush all remaining spans."""
        self._running = False

        # Flush batch processor
        await self._batch_processor.shutdown()

        # Flush remaining queue
        batch = self._queue.drain()
        if batch:
            await self._export_batch(batch)

        # Flush export manager
        await self._export_manager.flush()
        await self._export_manager.shutdown()

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return {
            "running": self._running,
            "queue": self._queue.get_stats(),
            "buffer": self._buffer.get_stats(),
            "compression": self._compression.get_stats(),
            "retry": self._retry.get_stats(),
            "timeout": self._timeout.get_stats(),
            "exporters": self._export_manager.get_stats(),
            "metrics": self._metrics.get_stats(),
        }
