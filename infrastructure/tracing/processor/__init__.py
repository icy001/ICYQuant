"""
Span processor package.

Provides batch processing, queuing, retry,
compression, timeout, and buffering for
the trace export pipeline.

Components:
- BatchProcessor: Batches spans for export
- SpanQueue: FIFO queue with overflow protection
- RetryPolicy: Exponential backoff retry
- CompressionManager: gzip/zstd/snappy compression
- TimeoutController: Export timeout with cancellation
- SpanBuffer: Memory + disk buffer for recovery
- ProcessorFactory: Creates span processors
"""

from .batch import BatchProcessor
from .buffer import SpanBuffer
from .compression import CompressionManager
from .factory import ProcessorFactory
from .queue import SpanQueue
from .retry import RetryPolicy
from .timeout import TimeoutController

__all__ = [
    "BatchProcessor",
    "SpanBuffer",
    "CompressionManager",
    "SpanQueue",
    "RetryPolicy",
    "TimeoutController",
    "ProcessorFactory",
]
