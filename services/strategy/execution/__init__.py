"""Strategy execution session, intent boundary and risk handoff package.

The strategy domain stops at the intent boundary: a strategy may express an
execution intent but can never create an order, reach the OMS or touch a
broker.  The core boundary::

    Signal != Execution Intent != Order Request

    Strategy -> Signal -> Execution Intent (strategy domain stops here)
                              |
                              v
                  Risk Engine -> Order Request -> Execution Engine

Once an intent is validated it is handed to the risk domain through the
guarded, idempotent :class:`RiskHandoff` crossing.  Every intent carries full
lineage (strategy / session / signal / intent / correlation ids) so a single
``correlation_id`` can trace a trade from signal to fill.
"""

from services.strategy.execution.boundary import (
    ExecutionIntentBoundary,
    InMemoryIntentStore,
    IntentStore,
)
from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.handoff import (
    HANDOFF_EVENTS,
    INTENT_CANCELLED,
    INTENT_EXPIRED,
    INTENT_NOT_VALIDATED,
    READINESS_BLOCKED,
    SESSION_NOT_ACTIVE,
    RiskHandoff,
    RiskHandoffRequest,
    RiskHandoffResult,
    new_decision_id,
)
from services.strategy.execution.intent import (
    SUPPORTED_EXECUTION_POLICIES,
    SUPPORTED_SIDES,
    SUPPORTED_URGENCIES,
    TERMINAL_INTENT_STATES,
    ExecutionIntent,
    ExecutionIntentState,
    StrategySignal,
    intent_fingerprint,
    intent_state_value,
    is_terminal,
    new_intent_id,
)
from services.strategy.execution.lifecycle import (
    IntentLifecycle,
    IntentLifecycleError,
)
from services.strategy.execution.lineage import (
    ExecutionLineage,
    lineage_from_intent,
    new_correlation_id,
)
from services.strategy.execution.policy import ExecutionPolicy
from services.strategy.execution.result import IntentResult
from services.strategy.execution.session import (
    SESSION_TRANSITIONS,
    ExecutionSessionError,
    ExecutionSessionState,
    StrategyExecutionSession,
    new_session_id,
    session_state_value,
)
from services.strategy.execution.snapshot import (
    IntentSnapshot,
    snapshot_intent,
)
from services.strategy.execution.validator import (
    IntentValidationError,
    IntentValidator,
)

__all__ = [
    "ExecutionContext",
    "ExecutionIntent",
    "ExecutionIntentBoundary",
    "ExecutionIntentState",
    "ExecutionLineage",
    "ExecutionPolicy",
    "ExecutionSessionError",
    "ExecutionSessionState",
    "HANDOFF_EVENTS",
    "INTENT_CANCELLED",
    "INTENT_EXPIRED",
    "INTENT_NOT_VALIDATED",
    "InMemoryIntentStore",
    "IntentLifecycle",
    "IntentLifecycleError",
    "IntentResult",
    "IntentSnapshot",
    "IntentStore",
    "IntentValidationError",
    "IntentValidator",
    "READINESS_BLOCKED",
    "RiskHandoff",
    "RiskHandoffRequest",
    "RiskHandoffResult",
    "SESSION_NOT_ACTIVE",
    "SESSION_TRANSITIONS",
    "SUPPORTED_EXECUTION_POLICIES",
    "SUPPORTED_SIDES",
    "SUPPORTED_URGENCIES",
    "StrategyExecutionSession",
    "StrategySignal",
    "TERMINAL_INTENT_STATES",
    "intent_fingerprint",
    "intent_state_value",
    "is_terminal",
    "lineage_from_intent",
    "new_correlation_id",
    "new_decision_id",
    "new_intent_id",
    "new_session_id",
    "session_state_value",
    "snapshot_intent",
]
