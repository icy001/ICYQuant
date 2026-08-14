"""Strategy execution readiness package.

Separates "the strategy is running" from "the strategy may produce execution
intents".  The execution readiness gate is the last system-level barrier
before signal generation::

    Strategy RUNNING != Strategy EXECUTION READY

    Lifecycle RUNNING AND Runtime RUNNING AND Readiness READY
        ==> Execution Eligible
"""

from services.strategy.readiness.checks import (
    DEFAULT_READINESS_CHECKS,
    CheckResult,
    ConfigurationCheck,
    ExecutionConnectivityCheck,
    LifecycleCheck,
    MarketDataReadinessCheck,
    ReadinessCheck,
    RiskReadinessCheck,
    RuntimeCheck,
)
from services.strategy.readiness.execution_gate import ExecutionReadinessGate
from services.strategy.readiness.gate import (
    READINESS_EVENTS,
    ReadinessCache,
    ReadinessTracker,
    StrategyExecutionReadinessGate,
    can_execute,
)
from services.strategy.readiness.policy import ReadinessPolicy
from services.strategy.readiness.result import ReadinessResult
from services.strategy.readiness.state import (
    EXECUTABLE_STATES,
    ExecutionReadiness,
    ReadinessContext,
    is_executable,
    new_evaluation_id,
    readiness_state_value,
)

__all__ = [
    "CheckResult",
    "ConfigurationCheck",
    "DEFAULT_READINESS_CHECKS",
    "EXECUTABLE_STATES",
    "ExecutionConnectivityCheck",
    "ExecutionReadiness",
    "ExecutionReadinessGate",
    "LifecycleCheck",
    "MarketDataReadinessCheck",
    "READINESS_EVENTS",
    "ReadinessCache",
    "ReadinessCheck",
    "ReadinessContext",
    "ReadinessPolicy",
    "ReadinessResult",
    "ReadinessTracker",
    "RiskReadinessCheck",
    "RuntimeCheck",
    "StrategyExecutionReadinessGate",
    "can_execute",
    "is_executable",
    "new_evaluation_id",
    "readiness_state_value",
]
