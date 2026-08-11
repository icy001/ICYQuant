"""
Streaming Engine — central orchestrator for the enterprise real-time
streaming platform with pub/sub, processing, checkpointing and fault tolerance.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

from .streaming_runtime import StreamingRuntime, StreamingRuntimeConfig
from .stream_manager import StreamManager, StreamStatus
from .stream_controller import StreamController
from .topic_registry import TopicRegistry, TopicEntry, TopicStatus
from .partition_manager import PartitionManager
from .publisher import Publisher, PublishResult
from .subscriber import Subscriber
from .stream_pipeline import StreamPipeline
from .event_router import EventRouter
from .checkpoint_manager import CheckpointManager
from .exactly_once_engine import ExactlyOnceEngine
from .backpressure_controller import BackpressureController
from .metrics import StreamingMetrics
from .telemetry import StreamingTelemetry
from .diagnostics import StreamingDiagnostics
from .health import StreamingHealthChecker, StreamingHealthStatus

logger = logging.getLogger(__name__)


class StreamingState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class StreamingConfig:
    """Configuration for the streaming platform."""
    platform_id: str = "icyquant-streaming"
    max_topics: int = 1000
    max_partitions_per_topic: int = 256
    default_partition_count: int = 4
    runtime: StreamingRuntimeConfig = field(default_factory=StreamingRuntimeConfig)
    enable_checkpointing: bool = True
    checkpoint_interval_ms: int = 10000
    enable_exactly_once: bool = True
    enable_backpressure: bool = True
    enable_dlq: bool = True
    max_retry_attempts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


class StreamingEngine:
    """
    Central orchestrator for the enterprise real-time streaming platform.

    Manages all aspects of event streaming: topic lifecycle, publish/subscribe,
    stream processing pipelines, checkpointing, exactly-once delivery,
    backpressure control, and dead letter queues.

    Usage::

        engine = StreamingEngine(StreamingConfig())
        await engine.initialize()
        await engine.start()
        result = await engine.publish("market.tick", {"symbol": "BTC", "price": 50000})
        await engine.subscribe("market.tick", handle_tick)
    """

    def __init__(self, config: Optional[StreamingConfig] = None) -> None:
        self.config = config or StreamingConfig()
        self._platform_id = self.config.platform_id
        self._state = StreamingState.CREATED
        self._created_at = datetime.now(timezone.utc)

        # Subsystems (created lazily)
        self._runtime: Optional[StreamingRuntime] = None
        self._stream_manager: Optional[StreamManager] = None
        self._stream_controller: Optional[StreamController] = None
        self._topic_registry: Optional[TopicRegistry] = None
        self._partition_manager: Optional[PartitionManager] = None
        self._publisher: Optional[Publisher] = None
        self._subscriber: Optional[Subscriber] = None
        self._event_router: Optional[EventRouter] = None
        self._checkpoint_manager: Optional[CheckpointManager] = None
        self._exactly_once_engine: Optional[ExactlyOnceEngine] = None
        self._backpressure_controller: Optional[BackpressureController] = None

        # Observability
        self.metrics = StreamingMetrics()
        self.telemetry = StreamingTelemetry()
        self.diagnostics = StreamingDiagnostics()
        self.health = StreamingHealthChecker()

        # Active pipelines
        self._pipelines: dict[str, StreamPipeline] = {}

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the streaming engine and all subsystems."""
        self._state = StreamingState.INITIALIZING
        logger.info("Initializing StreamingEngine [%s]", self._platform_id)

        self._runtime = StreamingRuntime(self.config.runtime)
        self._topic_registry = TopicRegistry()
        self._partition_manager = PartitionManager(
            self.config.default_partition_count,
            self.config.max_partitions_per_topic,
        )
        self._stream_manager = StreamManager()
        self._stream_controller = StreamController()
        self._publisher = Publisher(self.metrics, self.telemetry)
        self._subscriber = Subscriber(self.metrics)
        self._event_router = EventRouter()

        if self.config.enable_checkpointing:
            self._checkpoint_manager = CheckpointManager(
                checkpoint_interval_ms=self.config.checkpoint_interval_ms,
            )
            await self._checkpoint_manager.initialize()

        if self.config.enable_exactly_once:
            self._exactly_once_engine = ExactlyOnceEngine()

        if self.config.enable_backpressure:
            self._backpressure_controller = BackpressureController()

        await self.health.initialize()
        await self.telemetry.initialize()
        await self.diagnostics.initialize()

        # Inject components for diagnostics
        self.diagnostics.inject("streaming_engine", self)
        self.diagnostics.inject("topic_registry", self._topic_registry)
        self.diagnostics.inject("publisher", self._publisher)
        self.diagnostics.inject("subscriber", self._subscriber)

        self.health.inject_component("streaming_engine", self)
        self.health.inject_component("topic_registry", self._topic_registry)

        self._state = StreamingState.RUNNING
        logger.info("StreamingEngine initialized and running.")

    async def start(self) -> None:
        """Start the streaming engine."""
        if self._state != StreamingState.RUNNING:
            await self.initialize()
        logger.info("StreamingEngine started.")

    async def stop(self) -> None:
        """Stop the streaming engine gracefully."""
        self._state = StreamingState.STOPPING
        logger.info("Stopping StreamingEngine...")

        for pipe_id, pipeline in list(self._pipelines.items()):
            await pipeline.stop()
        self._pipelines.clear()

        if self._runtime:
            await self._runtime.stop()
        if self._checkpoint_manager:
            await self._checkpoint_manager.stop()

        await self.health.stop()
        await self.telemetry.stop()
        await self.diagnostics.stop()

        self._state = StreamingState.STOPPED
        logger.info("StreamingEngine stopped.")

    # ── Topic Management ──────────────────────────────────────────

    async def create_topic(
        self,
        name: str,
        partitions: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TopicEntry:
        """Create a new topic in the streaming platform."""
        if self._topic_registry is None:
            raise RuntimeError("StreamingEngine not initialized")

        entry = await self._topic_registry.register(
            name=name,
            partitions=partitions or self.config.default_partition_count,
            metadata=metadata or {},
        )

        if self._partition_manager is not None:
            await self._partition_manager.create_partitions(
                topic=name,
                count=partitions or self.config.default_partition_count,
            )

        self.metrics.record_topic_created(name)
        logger.info("Topic created: %s (%d partitions)", name, entry.partition_count)
        return entry

    async def delete_topic(self, name: str) -> bool:
        """Delete a topic."""
        if self._topic_registry is None:
            return False
        result = await self._topic_registry.delete(name)
        if result:
            self.metrics.record_topic_deleted(name)
        return result

    async def list_topics(self) -> list[TopicEntry]:
        """List all registered topics."""
        if self._topic_registry is None:
            return []
        return await self._topic_registry.list_all()

    # ── Publish / Subscribe ───────────────────────────────────────

    async def publish(
        self,
        topic: str,
        payload: Any,
        *,
        key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> PublishResult:
        """Publish an event to a topic."""
        if self._publisher is None:
            raise RuntimeError("StreamingEngine not initialized")

        trace, span = self.telemetry.trace_publish(topic)
        try:
            result = await self._publisher.publish(
                topic=topic,
                payload=payload,
                key=key,
                headers=headers,
            )
            self.metrics.record_publish(topic, result.success)
            return result
        finally:
            self.telemetry.end_span(span.span_id)
            self.telemetry.end_trace(trace.trace_id)

    async def publish_batch(
        self,
        topic: str,
        events: list[Any],
        *,
        keys: Optional[list[str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> list[PublishResult]:
        """Publish a batch of events to a topic."""
        if self._publisher is None:
            raise RuntimeError("StreamingEngine not initialized")

        results = await self._publisher.publish_batch(
            topic=topic,
            events=events,
            keys=keys,
            headers=headers,
        )
        for r in results:
            self.metrics.record_publish(topic, r.success)
        return results

    async def subscribe(
        self,
        topic: str,
        handler: Any,
        *,
        group_id: Optional[str] = None,
        mode: str = "latest",
    ) -> str:
        """Subscribe to a topic with a handler function.

        Returns a subscription ID for cancellation.
        """
        if self._subscriber is None:
            raise RuntimeError("StreamingEngine not initialized")

        sub_id = await self._subscriber.subscribe(
            topic=topic,
            handler=handler,
            group_id=group_id,
            mode=mode,
        )
        self.metrics.record_subscription(topic, "subscribe")
        logger.info("Subscribed to %s (sub_id=%s, group=%s)", topic, sub_id[:8], group_id)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a topic."""
        if self._subscriber is None:
            return False
        return await self._subscriber.unsubscribe(subscription_id)

    # ── Pipeline Management ───────────────────────────────────────

    async def create_pipeline(self, name: str, stages: list[Any]) -> StreamPipeline:
        """Create and register a stream processing pipeline."""
        pipeline = StreamPipeline(name=name, stages=stages)
        self._pipelines[name] = pipeline
        await pipeline.initialize()
        logger.info("Pipeline created: %s (%d stages)", name, len(stages))
        return pipeline

    async def start_pipeline(self, name: str) -> None:
        """Start a registered pipeline."""
        pipeline = self._pipelines.get(name)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {name}")
        await pipeline.start()

    async def stop_pipeline(self, name: str) -> None:
        """Stop a registered pipeline."""
        pipeline = self._pipelines.get(name)
        if pipeline:
            await pipeline.stop()

    # ── Stream Processing ─────────────────────────────────────────

    async def process_event(
        self,
        topic: str,
        event: Any,
        processor_id: Optional[str] = None,
    ) -> Any:
        """Process a single event through the event router."""
        if self._event_router is None:
            raise RuntimeError("StreamingEngine not initialized")

        return await self._event_router.route(topic, event, processor_id=processor_id)

    async def process_stream(
        self,
        topic: str,
        events: AsyncIterator[Any],
        processor_id: str,
    ) -> AsyncIterator[Any]:
        """Process a stream of events."""
        if self._event_router is None:
            raise RuntimeError("StreamingEngine not initialized")

        async for event in events:
            result = await self._event_router.route(topic, event, processor_id=processor_id)
            yield result

    # ── Checkpoint / Exactly-Once ─────────────────────────────────

    async def checkpoint(self, topic: str) -> Optional[str]:
        """Create a checkpoint for a topic."""
        if self._checkpoint_manager is None:
            return None
        return await self._checkpoint_manager.create_checkpoint(topic)

    async def restore_checkpoint(self, topic: str, checkpoint_id: str) -> bool:
        """Restore state from a checkpoint."""
        if self._checkpoint_manager is None:
            return False
        return await self._checkpoint_manager.restore(topic, checkpoint_id)

    # ── Backpressure ──────────────────────────────────────────────

    async def set_backpressure_limit(self, topic: str, limit: int) -> None:
        """Set backpressure limit for a topic."""
        if self._backpressure_controller is not None:
            await self._backpressure_controller.set_limit(topic, limit)

    # ── Status & Observability ────────────────────────────────────

    @property
    def state(self) -> StreamingState:
        return self._state

    async def status(self) -> dict[str, Any]:
        """Get the full status of the streaming platform."""
        return {
            "platform_id": self._platform_id,
            "state": self._state.value,
            "topics": await self._topic_registry.count() if self._topic_registry else 0,
            "pipelines": len(self._pipelines),
            "active_subscriptions": await self._subscriber.active_count() if self._subscriber else 0,
            "metrics": self.metrics.to_dict(),
            "health": await self.health.check_all() if self.health else None,
        }

    async def health_check(self) -> StreamingHealthStatus:
        """Run a health check on the streaming platform."""
        report = await self.health.readiness()
        return report.overall_status

    async def diagnostics_report(self) -> dict[str, Any]:
        """Run full diagnostics."""
        report = await self.diagnostics.run_full_diagnostics()
        return {
            "status": report.overall_status.value,
            "checks": [{"name": c.name, "status": c.status.value, "message": c.message} for c in report.checks],
            "summary": report.summary,
        }
