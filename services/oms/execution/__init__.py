"""OMS execution package — execution gateway integration."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "ExecutionGateway": ".execution_gateway",
        "InMemoryExecutionGateway": ".execution_gateway",
        "ExecutionRequest": ".execution_request",
        "CancelRequest": ".execution_request",
        "ExecutionAck": ".execution_response",
        "CancelAck": ".execution_response",
        "ExecutionReport": ".execution_report",
        "ExecutionStatus": ".execution_status",
        "ExecutionError": ".execution_error",
        "ExecutionTimeoutError": ".execution_error",
        "ExecutionUnknownError": ".execution_error",
        "RequestIdReuseConflictError": ".execution_error",
        "ExecutionQuantityExceededError": ".execution_error",
        "ExecutionRouter": ".execution_router",
        "ExecutionAckHandler": ".execution_ack_handler",
        "ExecutionReportHandler": ".execution_report_handler",
        "ExecutionRecovery": ".execution_recovery",
        "RecoveryTrigger": ".execution_recovery",
        "RecoveryResult": ".execution_recovery",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "ExecutionGateway", "InMemoryExecutionGateway",
    "ExecutionRequest", "CancelRequest",
    "ExecutionAck", "CancelAck",
    "ExecutionReport", "ExecutionStatus",
    "ExecutionError", "ExecutionTimeoutError", "ExecutionUnknownError",
    "RequestIdReuseConflictError", "ExecutionQuantityExceededError",
    "ExecutionRouter", "ExecutionAckHandler", "ExecutionReportHandler",
    "ExecutionRecovery", "RecoveryTrigger", "RecoveryResult",
]
