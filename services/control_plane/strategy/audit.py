"""
Strategy Control audit — every state transition must produce an audit event
(Commit 26 Part 1.3, spec section 27).

Each event is correlated with the originating incident, the control that was
applied, the actor who performed the change and the reason, forming the
tractable chain:

    Incident → Control → Portfolio → Strategy → Order
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .state import StrategyState


class StrategyControlAuditEventType(str, Enum):

    STRATEGY_RESUMED = "STRATEGY_RESUMED"

    STRATEGY_PAUSED = "STRATEGY_PAUSED"

    STRATEGY_DRAINING = "STRATEGY_DRAINING"

    STRATEGY_DISABLED = "STRATEGY_DISABLED"

    STRATEGY_RECOVERING = "STRATEGY_RECOVERING"


def audit_event_type_for(state: StrategyState) -> StrategyControlAuditEventType:
    """Map a target StrategyState to the audit event it produces."""
    if state is StrategyState.RUNNING:
        return StrategyControlAuditEventType.STRATEGY_RESUMED
    if state is StrategyState.PAUSED:
        return StrategyControlAuditEventType.STRATEGY_PAUSED
    if state is StrategyState.DRAINING:
        return StrategyControlAuditEventType.STRATEGY_DRAINING
    if state is StrategyState.DISABLED:
        return StrategyControlAuditEventType.STRATEGY_DISABLED
    return StrategyControlAuditEventType.STRATEGY_RECOVERING


@dataclass(frozen=True)
class StrategyControlAuditRecord:

    event_type: StrategyControlAuditEventType

    strategy_id: str

    previous_state: StrategyState | None

    new_state: StrategyState

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    actor: str = "strategy-controller"

    reason: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
