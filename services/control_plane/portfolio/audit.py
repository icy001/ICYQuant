"""
Portfolio Control audit — every state transition must produce an audit event
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

from .state import PortfolioState


class PortfolioControlAuditEventType(str, Enum):

    PORTFOLIO_ACTIVATED = "PORTFOLIO_ACTIVATED"

    PORTFOLIO_RESTRICTED = "PORTFOLIO_RESTRICTED"

    PORTFOLIO_REDUCE_ONLY = "PORTFOLIO_REDUCE_ONLY"

    PORTFOLIO_FROZEN = "PORTFOLIO_FROZEN"

    PORTFOLIO_LIQUIDATING = "PORTFOLIO_LIQUIDATING"

    PORTFOLIO_RECOVERING = "PORTFOLIO_RECOVERING"


def audit_event_type_for(state: PortfolioState) -> PortfolioControlAuditEventType:
    """Map a target PortfolioState to the audit event it produces."""
    if state is PortfolioState.ACTIVE:
        return PortfolioControlAuditEventType.PORTFOLIO_ACTIVATED
    if state is PortfolioState.RESTRICTED:
        return PortfolioControlAuditEventType.PORTFOLIO_RESTRICTED
    if state is PortfolioState.REDUCE_ONLY:
        return PortfolioControlAuditEventType.PORTFOLIO_REDUCE_ONLY
    if state is PortfolioState.FROZEN:
        return PortfolioControlAuditEventType.PORTFOLIO_FROZEN
    if state is PortfolioState.LIQUIDATING:
        return PortfolioControlAuditEventType.PORTFOLIO_LIQUIDATING
    return PortfolioControlAuditEventType.PORTFOLIO_RECOVERING


@dataclass(frozen=True)
class PortfolioControlAuditRecord:

    event_type: PortfolioControlAuditEventType

    portfolio_id: str

    previous_state: PortfolioState | None

    new_state: PortfolioState

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    actor: str = "portfolio-controller"

    reason: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
