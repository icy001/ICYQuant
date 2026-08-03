"""
Kafka infrastructure.

Provides production-grade Kafka infrastructure
for the ICYQuant event-driven architecture,
including event bus, producer, consumer,
health checking, and serialization.
"""

from .bootstrap import (
    KafkaBootstrap,
    KafkaTracing,
)
from .client import KafkaClient
from .config import KafkaConfig
from .consumer import (
    KafkaConsumerService,
    ConsumerRebalanceListener,
)
from .deadletter import (
    DeadLetterMessage,
)
from .envelope import (
    EventEnvelope,
)
from .eventbus import (
    EventBus,
    EventHandler,
)
from .exceptions import (
    KafkaError,
    KafkaConnectionError,
    KafkaPublishError,
    KafkaConsumeError,
    KafkaSerializationError,
)
from .health import KafkaHealth
from .metrics import (
    ConsumerMetrics,
    KafkaMetricsExporter,
    ProducerMetrics,
)
from .producer import (
    KafkaProducerService,
)
from .registry import (
    TopicRegistry,
)
from .retry import (
    RetryPolicy,
)
from .router import (
    EventRouter,
)
from .serializer import (
    JsonSerializer,
)

__all__ = [
    # Bootstrap
    "KafkaBootstrap",
    "KafkaTracing",
    # Core
    "KafkaClient",
    "KafkaConfig",
    "KafkaConsumerService",
    "ConsumerRebalanceListener",
    "KafkaHealth",
    "KafkaProducerService",
    "ConsumerMetrics",
    "KafkaMetricsExporter",
    "ProducerMetrics",
    "JsonSerializer",
    # Event Bus
    "EventBus",
    "EventHandler",
    "EventEnvelope",
    "EventRouter",
    "TopicRegistry",
    "RetryPolicy",
    "DeadLetterMessage",
    # Exceptions
    "KafkaError",
    "KafkaConnectionError",
    "KafkaPublishError",
    "KafkaConsumeError",
    "KafkaSerializationError",
]
