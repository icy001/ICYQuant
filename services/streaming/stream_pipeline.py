"""
Stream Pipeline — composable event processing pipeline with
stages, branching, and error handling.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .stream_processor import StreamProcessor, ProcessorStatus

logger = logging.getLogger(__name__)


class PipelineStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStage:
    """A single stage in a stream pipeline."""
    name: str
    processor: StreamProcessor
    status: PipelineStageStatus = PipelineStageStatus.PENDING
    error_handler: Optional[Any] = None
    condition: Optional[Any] = None  # Optional predicate to skip stage
    metadata: dict[str, Any] = field(default_factory=dict)


class StreamPipeline:
    """
    Composable event processing pipeline.

    Chains processors together in stages, passing output from one
    stage as input to the next. Supports conditional stages,
    error handling, and branching.

    Pipeline flow:
        Publish → Deserialize → Process → Window → Aggregate → Enrich → Publish

    Usage::

        pipeline = StreamPipeline("market_data_pipeline", [
            PipelineStage("deserialize", deserializer),
            PipelineStage("validate", validator),
            PipelineStage("enrich", enricher),
        ])
        await pipeline.initialize()
        results = await pipeline.execute(event)
    """

    def __init__(
        self,
        name: str,
        stages: list[PipelineStage],
        *,
        stop_on_error: bool = False,
        parallel: bool = False,
    ) -> None:
        self.name = name
        self.stages = stages
        self.stop_on_error = stop_on_error
        self.parallel = parallel
        self._status = ProcessorStatus.CREATED
        self._execution_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

    async def initialize(self) -> None:
        """Initialize all pipeline stages."""
        self._status = ProcessorStatus.INITIALIZING
        for stage in self.stages:
            await stage.processor.initialize()
            stage.status = PipelineStageStatus.PENDING
        self._status = ProcessorStatus.RUNNING
        logger.info("Pipeline %s initialized with %d stages.", self.name, len(self.stages))

    async def start(self) -> None:
        """Start the pipeline."""
        if self._status != ProcessorStatus.RUNNING:
            await self.initialize()
        logger.info("Pipeline %s started.", self.name)

    async def stop(self) -> None:
        """Stop the pipeline."""
        self._status = ProcessorStatus.STOPPING
        for stage in self.stages:
            await stage.processor.stop()
        self._status = ProcessorStatus.STOPPED
        logger.info("Pipeline %s stopped.", self.name)

    async def execute(self, event: Any) -> list[dict[str, Any]]:
        """Execute the full pipeline on an event."""
        start = time.monotonic()
        results: list[dict[str, Any]] = []
        current = event
        self._execution_count += 1

        for stage in self.stages:
            stage_start = time.monotonic()

            # Check condition
            if stage.condition:
                try:
                    if callable(stage.condition):
                        should_run = stage.condition(current)
                    else:
                        should_run = True
                    if not should_run:
                        stage.status = PipelineStageStatus.SKIPPED
                        results.append({
                            "stage": stage.name,
                            "status": PipelineStageStatus.SKIPPED.value,
                        })
                        continue
                except Exception:
                    pass

            try:
                stage.status = PipelineStageStatus.RUNNING
                proc_result = await stage.processor.handle(current)

                if proc_result.success:
                    stage.status = PipelineStageStatus.COMPLETED
                    current = proc_result.output if proc_result.output is not None else current
                else:
                    stage.status = PipelineStageStatus.FAILED
                    self._error_count += 1
                    if stage.error_handler:
                        current = await self._handle_error(stage, proc_result)
                    elif self.stop_on_error:
                        results.append({
                            "stage": stage.name,
                            "status": "failed",
                            "error": proc_result.error,
                        })
                        break

            except Exception as e:
                stage.status = PipelineStageStatus.FAILED
                self._error_count += 1
                logger.error("Pipeline %s stage %s error: %s", self.name, stage.name, e)
                if self.stop_on_error:
                    results.append({
                        "stage": stage.name,
                        "status": "failed",
                        "error": str(e),
                    })
                    break

            stage_latency = (time.monotonic() - stage_start) * 1000
            results.append({
                "stage": stage.name,
                "status": stage.status.value,
                "latency_ms": round(stage_latency, 3),
            })

        total_latency = (time.monotonic() - start) * 1000
        self._total_latency_ms += total_latency
        return results

    async def execute_batch(self, events: list[Any]) -> list[list[dict[str, Any]]]:
        """Execute the pipeline on a batch of events."""
        if self.parallel:
            tasks = [self.execute(e) for e in events]
            return await asyncio.gather(*tasks)
        else:
            return [await self.execute(e) for e in events]

    async def _handle_error(self, stage: PipelineStage, result: Any) -> Any:
        """Invoke error handler for a failed stage."""
        if stage.error_handler:
            if callable(stage.error_handler):
                return stage.error_handler(result)
            if asyncio.iscoroutinefunction(stage.error_handler):
                return await stage.error_handler(result)
        return result

    @property
    def status(self) -> ProcessorStatus:
        return self._status

    async def stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "name": self.name,
            "status": self._status.value,
            "stages": len(self.stages),
            "executions": self._execution_count,
            "errors": self._error_count,
            "avg_latency_ms": round(
                self._total_latency_ms / max(self._execution_count, 1), 3
            ),
            "stage_details": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "processor_type": s.processor.config.processor_type.value,
                }
                for s in self.stages
            ],
        }
