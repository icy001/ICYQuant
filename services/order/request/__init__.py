"""Order request domain.

Commit 32 turns an authorized execution context into a normalized order
request::

    AuthorizedExecutionContext
        -> OrderRequestFactory
        -> OrderRequest
        -> OrderRequestValidator
        -> OrderRequestNormalizer
        -> NormalizedOrderRequest

The order request is not an order: the OMS has not accepted it and no broker /
exchange has seen it.  It preserves the full risk authorization lineage, fixes
quantity to the approved ceiling, and never re-runs risk evaluation.
"""

from services.order.request.contract import OrderRequestFactoryProtocol
from services.order.request.errors import (
    OrderRequestErrorCode,
    OrderRequestValidationError,
)
from services.order.request.exceptions import OrderRequestPersistenceError
from services.order.request.event_factory import (
    AGGREGATE_TYPE,
    OrderRequestEventFactory,
    new_event_id,
)
from services.order.request.event_publisher import (
    EventBus,
    EventBusUnavailable,
    InMemoryEventBus,
    OrderRequestEventPublisher,
    OrderRequestOutbox,
)
from services.order.request.event_types import OrderRequestEventType
from services.order.request.events import (
    OrderRequestEvent,
    OutboxRecord,
    OutboxStatus,
)
from services.order.request.factory import (
    OrderRequestFactory,
    authorization_idempotency_key,
    new_order_request_id,
)
from services.order.request.lifecycle import (
    InvalidStateTransition,
    OrderRequestLifecycle,
    OrderRequestStateTransition,
)
from services.order.request.model import (
    ORDER_TYPES,
    SIDES,
    TIME_IN_FORCE_VALUES,
    OrderRequest,
)
from services.order.request.repository import (
    InMemoryOrderRequestRepository,
    OrderRequestRepository,
    OrderRequestSnapshot,
)
from services.order.request.state import OrderRequestState
from services.order.request.normalization import (
    NormalizedOrderRequest,
    OrderRequestNormalizer,
)
from services.order.request.service import OrderRequestService
from services.order.request.validation import (
    OrderRequestValidationResult,
    OrderRequestValidator,
    is_valid_symbol,
)

__all__ = [
    "AGGREGATE_TYPE",
    "ORDER_TYPES",
    "SIDES",
    "TIME_IN_FORCE_VALUES",
    "EventBus",
    "EventBusUnavailable",
    "InMemoryEventBus",
    "InMemoryOrderRequestRepository",
    "InvalidStateTransition",
    "NormalizedOrderRequest",
    "OrderRequest",
    "OrderRequestErrorCode",
    "OrderRequestPersistenceError",
    "OrderRequestRepository",
    "OrderRequestSnapshot",
    "OrderRequestEvent",
    "OrderRequestEventFactory",
    "OrderRequestEventPublisher",
    "OrderRequestEventType",
    "OrderRequestFactory",
    "OrderRequestFactoryProtocol",
    "OrderRequestLifecycle",
    "OrderRequestNormalizer",
    "OrderRequestOutbox",
    "OrderRequestService",
    "OrderRequestState",
    "OrderRequestStateTransition",
    "OrderRequestValidationError",
    "OrderRequestValidationResult",
    "OrderRequestValidator",
    "OutboxRecord",
    "OutboxStatus",
    "authorization_idempotency_key",
    "is_valid_symbol",
    "new_event_id",
    "new_order_request_id",
]
