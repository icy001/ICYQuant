"""Order -> Execution boundary (Commit 33 Part 1.3).

The order engine decides *that* an order enters the submission flow; the
execution engine decides *how* it reaches the venue.  This package is the
stable contract between the two (request / response / gateway / adapter), so
FIX, broker REST, paper and simulation adapters can be swapped without ever
touching the order domain.
"""

from services.order.engine.execution.adapter import ExecutionAdapter
from services.order.engine.execution.contract import ExecutionGateway
from services.order.engine.execution.errors import (
    ExecutionError,
    ExecutionRejectedError,
    ExecutionTimeoutError,
    ExecutionUnavailableError,
    ExecutionUnknownError,
)
from services.order.engine.execution.gateway import FakeExecutionGateway
from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)

__all__ = [
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
    "FakeExecutionGateway",
]
