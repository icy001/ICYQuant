"""
ICYQuant Enterprise Real-Time Streaming Platform

Commit 16 Part 1.4

Unified event streaming with:
- Pub/Sub messaging (publisher, subscriber, consumer groups)
- Stream processing (stateful/stateless, pipelines)
- Windowed aggregations (tumbling, sliding, session, global)
- Exactly-once delivery semantics
- Backpressure control & dead letter queues
- Checkpoint-based fault tolerance
"""

from .streaming_engine import StreamingEngine, StreamingConfig, StreamingState
from .streaming_runtime import StreamingRuntime, StreamingRuntimeConfig
from .stream_manager import StreamManager, StreamStatus
from .stream_controller import StreamController
from .topic_registry import TopicRegistry, TopicEntry, TopicStatus
from .partition_manager import PartitionManager, Partition, PartitionAssignment
from .publisher import Publisher, PublishResult, PublishAck
from .subscriber import Subscriber, Subscription, SubscriptionMode
from .consumer_group import ConsumerGroup, ConsumerMember, OffsetCommit
from .stream_processor import StreamProcessor, ProcessorConfig
from .stateful_processor import StatefulProcessor
from .stateless_processor import StatelessProcessor
from .stream_pipeline import StreamPipeline, PipelineStage
from .event_router import EventRouter, RouteRule, RouteStrategy
from .event_dispatcher import EventDispatcher, DispatchResult
from .event_serializer import EventSerializer, SerializationFormat
from .schema_registry import SchemaRegistry, SchemaEntry, SchemaVersion
from .enrichment_engine import EnrichmentEngine, EnrichmentSource
from .watermark_manager import WatermarkManager, Watermark, LateEventPolicy
from .state_store import StateStore, StateValue, StateTransaction
from .checkpoint_manager import CheckpointManager, CheckpointRecord, CheckpointMode
from .exactly_once_engine import ExactlyOnceEngine, DeliveryGuarantee
from .dead_letter_queue import DeadLetterQueue, DLQEntry, DLQStatus
from .retry_manager import RetryManager, RetryPolicy, RetryStrategy
from .backpressure_controller import BackpressureController, BackpressureStrategy

from .metrics import StreamingMetrics
from .telemetry import StreamingTelemetry, StreamSpan, StreamTrace
from .diagnostics import StreamingDiagnostics, StreamingDiagnosticCheck
from .health import StreamingHealthChecker, StreamingHealthStatus

__all__ = [
    # Core
    "StreamingEngine", "StreamingConfig", "StreamingState",
    "StreamingRuntime", "StreamingRuntimeConfig",
    "StreamManager", "StreamStatus",
    "StreamController",
    # Topics & Partitions
    "TopicRegistry", "TopicEntry", "TopicStatus",
    "PartitionManager", "Partition", "PartitionAssignment",
    # Pub/Sub
    "Publisher", "PublishResult", "PublishAck",
    "Subscriber", "Subscription", "SubscriptionMode",
    "ConsumerGroup", "ConsumerMember", "OffsetCommit",
    # Processing
    "StreamProcessor", "ProcessorConfig",
    "StatefulProcessor", "StatelessProcessor",
    "StreamPipeline", "PipelineStage",
    # Event Routing
    "EventRouter", "RouteRule", "RouteStrategy",
    "EventDispatcher", "DispatchResult",
    "EventSerializer", "SerializationFormat",
    "SchemaRegistry", "SchemaEntry", "SchemaVersion",
    # Enrichment
    "EnrichmentEngine", "EnrichmentSource",
    "WatermarkManager", "Watermark", "LateEventPolicy",
    # State & Checkpoint
    "StateStore", "StateValue", "StateTransaction",
    "CheckpointManager", "CheckpointRecord", "CheckpointMode",
    # Reliability
    "ExactlyOnceEngine", "DeliveryGuarantee",
    "DeadLetterQueue", "DLQEntry", "DLQStatus",
    "RetryManager", "RetryPolicy", "RetryStrategy",
    "BackpressureController", "BackpressureStrategy",
    # Observability
    "StreamingMetrics",
    "StreamingTelemetry", "StreamSpan", "StreamTrace",
    "StreamingDiagnostics", "StreamingDiagnosticCheck",
    "StreamingHealthChecker", "StreamingHealthStatus",
]
