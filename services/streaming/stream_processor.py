"""
Stream Processor — base processor interface for the streaming platform,
defining the standard event processing contract.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProcessorType(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


class ProcessorStatus(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ProcessorConfig:
    """Configuration for a stream processor."""
    processor_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    processor_type: ProcessorType = ProcessorType.STATELESS
    parallelism: int = 1
    buffer_size: int = 10000
    enable_metrics: bool = True
    max_retries: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result of processing a single event."""
    event_id: str
    success: bool = True
    output: Any = None
    latency_ms: float = 0.0
    error: str = ""


class StreamProcessor(ABC):
    """
    Abstract base for all stream processors.

    Defines the standard event processing contract that all
    processors (stateful and stateless) must implement.

    Usage::

        class TickProcessor(StreamProcessor):
            async def process(self, event):
                return ProcessingResult(event_id=event["id"], output=event)
    """

    def __init__(self, config: Optional[ProcessorConfig] = None) -> None:
        self.config = config or ProcessorConfig()
        self._status = ProcessorStatus.CREATED
        self._processed_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

    async def initialize(self) -> None:
        """Initialize the processor."""
        self._status = ProcessorStatus.INITIALIZING
        logger.info("Processor %s initializing.", self.config.processor_id[:8])
        self._status = ProcessorStatus.RUNNING

    async def stop(self) -> None:
        """Stop the processor."""
        self._status = ProcessorStatus.STOPPING
        logger.info("Processor %s stopping.", self.config.processor_id[:8])
        self._status = ProcessorStatus.STOPPED

    async def handle(self, event: Any) -> ProcessingResult:
        """Handle an event and record metrics."""
        start = time.monotonic()
        try:
            result = await self.process(event)
            if result.success:
                self._processed_count += 1
            else:
                self._error_count += 1
            result.latency_ms = (time.monotonic() - start) * 1000
            self._total_latency_ms += result.latency_ms
            return result
        except Exception as e:
            self._error_count += 1
            return ProcessingResult(
                event_id=getattr(event, "event_id", str(uuid.uuid4())),
                success=False,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(e),
            )

    @abstractmethod
    async def process(self, event: Any) -> ProcessingResult:
        """Process a single event. Subclasses must implement."""
        ...

    async def batch_process(self, events: list[Any]) -> list[ProcessingResult]:
        """Process a batch of events."""
        return [await self.handle(e) for e in events]

    @property
    def status(self) -> ProcessorStatus:
        return self._status

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def avg_latency_ms(self) -> float:
        return self._total_latency_ms / max(self._processed_count, 1)

    async def stats(self) -> dict[str, Any]:
        """Get processor statistics."""
        return {
            "processor_id": self.config.processor_id,
            "type": self.config.processor_type.value,
            "status": self._status.value,
            "processed": self._processed_count,
            "errors": self._error_count,
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "error_rate": self._error_count / max(self._processed_count, 1),
        }
