"""
Market recorder.
"""

from __future__ import annotations

from .batch_writer import BatchWriter
from .recording_metrics import RecordingMetrics


class MarketRecorder:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository
        self.writer = BatchWriter()
        self.metrics = RecordingMetrics()

    async def record(
        self,
        quote,
    ) -> None:
        self.writer.append(quote)
        batch = self.writer.flush()

        try:
            for item in batch:
                await self.repository.append_quote(item)
                self.metrics.recorded += 1
        except Exception:
            self.metrics.failed += len(batch)
            raise