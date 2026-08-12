"""
Execution Control — per-execution-channel capability gate
(Commit 26 Part 1.4).

Execution Control sits below Order Admission and above Venue Control,
deciding four capabilities independently:

    New Order
    Cancel Order
    Reduce Order
    Emergency Flatten

"禁止交易"不等于"禁止风险控制" — risk-reducing actions remain available.
"""

from .controller import ExecutionController
from .decision import ExecutionControlDecision
from .policy import ExecutionControlPolicy
from .request import ExecutionAction, ExecutionControlRequest
from .service import ExecutionControlService
from .state import ExecutionState
from .verdict import ExecutionResult, ExecutionVerdict

__all__ = [
    "ExecutionAction",
    "ExecutionControlDecision",
    "ExecutionControlPolicy",
    "ExecutionControlRequest",
    "ExecutionControlService",
    "ExecutionController",
    "ExecutionResult",
    "ExecutionState",
    "ExecutionVerdict",
]
