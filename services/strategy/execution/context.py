"""Execution context snapshot captured at intent creation time."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionContext:
    """System snapshot used when creating an execution intent.

    The context freezes the states that existed at intent creation time.  An
    intent created at 14:00:00 while the strategy was READY must remain
    understandable later, even if risk becomes BLOCKED at 14:00:02 - the
    snapshot records what the system looked like when the intent was made.

    ``readiness_checked_at`` records when the previous READY verdict was
    produced so the intent-time gate can expire stale verdicts
    (``0`` means "unknown / not enforced").
    """

    strategy_id: str

    lifecycle_state: str = "UNKNOWN"
    runtime_state: str = "UNKNOWN"
    readiness_state: str = "UNKNOWN"

    risk_state: str = "UNKNOWN"
    execution_state: str = "UNKNOWN"

    #: Execution session state at intent-creation time.  The risk handoff
    #: requires ACTIVE: an intent created while the session is PAUSED / CLOSING
    #: / CLOSED must never reach the risk engine even if the readiness gate
    #: still reports READY.
    session_state: str = "UNKNOWN"

    market_timestamp: float = 0.0
    readiness_checked_at: float = 0.0
    timestamp: float = field(default_factory=time.time)
