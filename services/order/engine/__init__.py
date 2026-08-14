"""Order engine (Commit 33 Part 1.1 / 1.2).

Turns a HANDOFF order request into an OMS :class:`Order` and drives its
lifecycle through the :class:`OrderEngineService` - the single application
boundary.  Business code must not talk to the factory, lifecycle or repository
directly.
"""

from services.order.engine.command import (
    AcceptOrderCommand,
    CancelOrderCommand,
    CreateOrderCommand,
    ExpireOrderCommand,
    RejectOrderCommand,
    SubmitOrderCommand,
)
from services.order.engine.execution.adapter import ExecutionAdapter
from services.order.engine.execution.contract import ExecutionGateway
from services.order.engine.execution.errors import (
    ExecutionError,
    ExecutionRejectedError,
    ExecutionTimeoutError,
    ExecutionUnavailableError,
    ExecutionUnknownError,
)
from services.order.engine.event_mapper import (
    EventEnvelope,
    EventMapper,
    EventMappingError,
)
from services.order.engine.event_publisher import (
    EventPublishError,
    InMemoryEventPublisher,
    OrderEventPublisher,
)
from services.order.engine.events import (
    EnvelopeBuildError,
    OrderEventEnvelope,
    envelope_from_event,
)
from services.order.engine.outbox import (
    DuplicateEventError,
    InMemoryOutboxPublisher,
    InMemoryOutboxRepository,
    OutboxDispatcher,
    OutboxError,
    OutboxMessage,
    OutboxMessageNotFoundError,
    OutboxPersistenceError,
    OutboxPublisher,
    OutboxPublishError,
    OutboxRecovery,
    OutboxRepository,
    OutboxService,
    OutboxStatus,
    RetryPolicy,
    validate_version,
)
from services.order.engine.execution.gateway import FakeExecutionGateway
from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)
from services.order.engine.factory import OrderCreationError, OrderFactory
from services.order.engine.lifecycle import OrderLifecycle
from services.order.engine.repository import (
    InMemoryOrderRepository,
    OrderPersistenceError,
    OrderRepository,
)
from services.order.engine.service import (
    OrderEngineService,
    OrderNotFoundError,
)
from services.order.engine.validator import (
    OrderValidationError,
    OrderValidator,
)

__all__ = [
    "AcceptOrderCommand",
    "CancelOrderCommand",
    "CreateOrderCommand",
    "DuplicateEventError",
    "EnvelopeBuildError",
    "EventEnvelope",
    "EventMapper",
    "EventMappingError",
    "EventPublishError",
    "ExecutionAdapter",
    "ExecutionError",
    "ExecutionGateway",
    "ExecutionRejectedError",
    "ExecutionRequest",
    "ExecutionResponse",
    "ExecutionResponseStatus",
    "ExecutionTimeoutError",
    "ExecutionUnavailableError",
    "ExecutionUnknownError",
    "ExpireOrderCommand",
    "FakeExecutionGateway",
    "InMemoryEventPublisher",
    "InMemoryOrderRepository",
    "InMemoryOutboxPublisher",
    "InMemoryOutboxRepository",
    "OrderCreationError",
    "OrderEngineService",
    "OrderEventEnvelope",
    "OrderFactory",
    "OrderLifecycle",
    "OrderNotFoundError",
    "OrderPersistenceError",
    "OrderRepository",
    "OrderValidationError",
    "OrderValidator",
    "OrderEventPublisher",
    "OutboxDispatcher",
    "OutboxError",
    "OutboxMessage",
    "OutboxMessageNotFoundError",
    "OutboxPersistenceError",
    "OutboxPublisher",
    "OutboxPublishError",
    "OutboxRecovery",
    "OutboxRepository",
    "OutboxService",
    "OutboxStatus",
    "RejectOrderCommand",
    "RetryPolicy",
    "SubmitOrderCommand",
    "envelope_from_event",
    "validate_version",
]
