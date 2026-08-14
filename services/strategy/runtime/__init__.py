"""Strategy runtime package.

Everything that speaks to the *actual* strategy runtime lives here: the
technology-neutral adapter seam, the runtime state enum and the heartbeat
protocol that feeds reconciliation.
"""

from services.strategy.runtime.adapter import (
    RuntimeActionError,
    StrategyRuntimeAdapter,
)
from services.strategy.runtime.readiness_adapter import (
    RuntimeReadinessAdapter,
    snapshot_to_context,
)
from services.strategy.runtime.heartbeat import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    HeartbeatTracker,
    RuntimeHeartbeat,
    utcnow,
)
from services.strategy.runtime.state import (
    ALIVE_STATES,
    HEALTHY_STATES,
    UNKNOWN_STATES,
    RuntimeState,
    runtime_state_value,
)

__all__ = [
    "ALIVE_STATES",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_HEARTBEAT_TIMEOUT_SECONDS",
    "HEALTHY_STATES",
    "UNKNOWN_STATES",
    "HeartbeatTracker",
    "RuntimeActionError",
    "RuntimeHeartbeat",
    "RuntimeReadinessAdapter",
    "RuntimeState",
    "StrategyRuntimeAdapter",
    "runtime_state_value",
    "snapshot_to_context",
    "utcnow",
]
