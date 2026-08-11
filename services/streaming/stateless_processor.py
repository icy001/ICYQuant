"""
Stateless Processor — lightweight event processor without persistent
state, optimized for throughput and low latency.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .stream_processor import (
    StreamProcessor,
    ProcessorConfig,
    ProcessorType,
    ProcessingResult,
)

logger = logging.getLogger(__name__)


class StatelessProcessor(StreamProcessor):
    """
    Lightweight stateless event processor.

    Each event is processed independently with no cross-event state.
    Optimized for high-throughput, low-latency scenarios like
    filtering, mapping, enrichment, and validation.

    Usage::

        class PriceFilter(StatelessProcessor):
            async def process(self, event):
                if event["price"] < 0:
                    return ProcessingResult(event_id=event["id"], success=False, error="Negative price")
                return ProcessingResult(event_id=event["id"], output=event)
    """

    def __init__(self, config: Optional[ProcessorConfig] = None) -> None:
        if config is None:
            config = ProcessorConfig(processor_type=ProcessorType.STATELESS)
        else:
            config.processor_type = ProcessorType.STATELESS
        super().__init__(config)

    async def process(self, event: Any) -> ProcessingResult:
        """Override in subclass to implement stateless logic."""
        raise NotImplementedError("Subclass must implement process()")
