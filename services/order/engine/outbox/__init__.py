"""Transactional outbox for reliable order event delivery (Commit 33 Part 1.5).

The outbox keeps order state and event publication inside the same transaction
boundary (#10): a command that saves the order also stages the event here; a
separate dispatcher then publishes to the bus, and recovery re-routes
unfinished messages.  Delivery model for this stage:

.. code-block:: text

    at-least-once delivery + idempotent consumer (#11)
"""

from services.order.engine.outbox.dispatcher import (
    InMemoryOutboxPublisher,
    OutboxDispatcher,
    OutboxPublisher,
)
from services.order.engine.outbox.errors import (
    DuplicateEventError,
    OutboxError,
    OutboxMessageNotFoundError,
    OutboxPersistenceError,
    OutboxPublishError,
)
from services.order.engine.outbox.model import (
    OutboxMessage,
    OutboxStatus,
    validate_version,
)
from services.order.engine.outbox.recovery import OutboxRecovery
from services.order.engine.outbox.repository import (
    InMemoryOutboxRepository,
    OutboxRepository,
)
from services.order.engine.outbox.retry import RetryPolicy
from services.order.engine.outbox.service import OutboxService

__all__ = [
    "DuplicateEventError",
    "InMemoryOutboxPublisher",
    "InMemoryOutboxRepository",
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
    "RetryPolicy",
    "validate_version",
]
