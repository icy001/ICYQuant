"""Strategy control boundary and lifecycle orchestration package.

Exposes the governed control surface for strategies: commands, state,
policies, validation, the boundary itself, control results, plus the
lifecycle orchestration layer that drives commands to completion at the
runtime and keeps control state synchronized with runtime state.
"""

from services.strategy.control.boundary import (
    CommandDispatcher,
    StrategyControlBoundary,
)
from services.strategy.control.commands import (
    KILL,
    PAUSE,
    RESUME,
    START,
    STOP,
    STRATEGY_CONTROL_ACTIONS,
    StrategyCommand,
    is_control_action,
)
from services.strategy.control.lifecycle import (
    CONTROL_PRIORITY,
    StrategyCommandArbiter,
)
from services.strategy.control.orchestrator import (
    EVENTS,
    OrchestrationResult,
    StrategyLifecycleMetrics,
    StrategyLifecycleOrchestrator,
)
from services.strategy.control.policies import (
    ACTION_TARGET_STATES,
    ALLOWED_ACTIONS_BY_STATE,
    StrategyControlPolicy,
    can_transition,
    target_state,
)
from services.strategy.control.result import StrategyControlResult
from services.strategy.control.state_store import (
    InMemoryStrategyStateStore,
    StrategyStateStore,
)
from services.strategy.control.synchronization import (
    ReconciliationResult,
    ReconciliationStatus,
    StrategyRuntimeSynchronizer,
    is_consistent,
    status_for,
)
from services.strategy.control.transition import StrategyTransition
from services.strategy.control.validator import StrategyControlValidator
from services.strategy.domain.control_state import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    StrategyControlState,
    is_active,
    is_terminal,
)

__all__ = [
    "ACTION_TARGET_STATES",
    "ACTIVE_STATES",
    "ALLOWED_ACTIONS_BY_STATE",
    "CONTROL_PRIORITY",
    "EVENTS",
    "KILL",
    "PAUSE",
    "RESUME",
    "START",
    "STOP",
    "STRATEGY_CONTROL_ACTIONS",
    "TERMINAL_STATES",
    "CommandDispatcher",
    "InMemoryStrategyStateStore",
    "OrchestrationResult",
    "ReconciliationResult",
    "ReconciliationStatus",
    "StrategyCommand",
    "StrategyCommandArbiter",
    "StrategyControlBoundary",
    "StrategyControlPolicy",
    "StrategyControlResult",
    "StrategyControlState",
    "StrategyControlValidator",
    "StrategyLifecycleMetrics",
    "StrategyLifecycleOrchestrator",
    "StrategyRuntimeSynchronizer",
    "StrategyStateStore",
    "StrategyTransition",
    "can_transition",
    "is_active",
    "is_consistent",
    "is_control_action",
    "is_terminal",
    "status_for",
    "target_state",
]
