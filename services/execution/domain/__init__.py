"""Execution domain (Commit 38).

The Execution domain owns *how an approved order is executed*:

.. code-block:: text

    ExecutionRequest  = "what to execute"
    ExecutionPolicy   = "how to execute it"
    ExecutionLifecycle= "what has happened to the execution"

The domain is deliberately decoupled from the OMS ``Order`` aggregate and from
any concrete Broker / Exchange adapter.
"""

from services.execution.domain.adapter_result import (
    AdapterOrderStatus,
    AdapterSubmissionResult,
)
from services.execution.domain.errors import (
    ExecutionAdapterError,
    ExecutionConnectionError,
    ExecutionConsumerError,
    ExecutionError,
    ExecutionSubmissionError,
    ExecutionTimeoutError,
    NonRetryableExecutionError,
    RetryableExecutionError,
)
from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.domain.checkpoint import (
    ReplayCheckpoint,
)
from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.domain.consumer_error import (
    ConsumerProcessingError,
)
from services.execution.domain.consumer_health import (
    ConsumerHealth,
    ConsumerHealthStatus,
)
from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)
from services.execution.domain.delivery import (
    DeliveryAttempt,
    DeliveryStatus,
)
from services.execution.domain.delivery_metrics import (
    DeliveryMetrics,
)
from services.execution.domain.event_sequence import (
    ExecutionEventSequence,
)
from services.execution.domain.fill import (
    ExecutionFill,
)
from services.execution.domain.journal import (
    ExecutionEventJournal,
)
from services.execution.domain.idempotency import (
    ExecutionIdempotencyKey,
)
from services.execution.domain.instruction import (
    ExecutionInstruction,
    ExecutionPolicy,
)
from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionRequestStatus,
    ExecutionSide,
)
from services.execution.domain.recovery import (
    RecoveryResult,
    RecoveryStatus,
)
from services.execution.domain.result import (
    ExecutionResult,
)
from services.execution.domain.routing import (
    ExecutionRoutingPolicy,
)
from services.execution.domain.sequence import (
    InvalidEventSequence,
    validate_next_sequence,
)
from services.execution.domain.state import (
    ExecutionState,
)
from services.execution.domain.transition import (
    ExecutionTransition,
    InvalidExecutionTransition,
)
from services.execution.domain.venue import (
    ExecutionVenue,
    ExecutionVenueType,
)

__all__ = [
    "AdapterOrderStatus",
    "AdapterSubmissionResult",
    "ConsumerHealth",
    "ConsumerHealthStatus",
    "ConsumerOffset",
    "ConsumerProcessingError",
    "DeadLetterEvent",
    "DeliveryAttempt",
    "DeliveryMetrics",
    "DeliveryStatus",
    "ExecutionAdapterError",
    "ExecutionConnectionError",
    "ExecutionConsumerError",
    "ExecutionError",
    "ExecutionEvent",
    "ExecutionEventJournal",
    "ExecutionEventSequence",
    "ExecutionEventType",
    "ExecutionFill",
    "ExecutionIdempotencyKey",
    "ExecutionInstruction",
    "ExecutionLifecycle",
    "ExecutionOrderType",
    "ExecutionPolicy",
    "ExecutionRequest",
    "ExecutionRequestStatus",
    "ExecutionResult",
    "ExecutionRoutingPolicy",
    "ExecutionSide",
    "ExecutionState",
    "ExecutionSubmissionError",
    "ExecutionTimeoutError",
    "ExecutionTransition",
    "ExecutionVenue",
    "ExecutionVenueType",
    "InvalidEventSequence",
    "InvalidExecutionTransition",
    "NonRetryableExecutionError",
    "RecoveryResult",
    "RecoveryStatus",
    "ReplayCheckpoint",
    "RetryPolicy",
    "RetryableExecutionError",
    "validate_next_sequence",
]
