"""Execution event consumers (Commit 39 Part 1.3).

Downstream services subscribe to the Execution event stream through
``ExecutionEventConsumer`` implementations.  Each consumer owns an independent
``ConsumerOffset`` inside its own domain: the Execution Domain only emits
events and never mutates downstream domains directly.
"""

from services.execution.consumers.ledger import (
    LedgerExecutionConsumer,
)
from services.execution.consumers.position import (
    PositionExecutionConsumer,
)

__all__ = [
    "LedgerExecutionConsumer",
    "PositionExecutionConsumer",
]
