"""
ReleaseKillSwitch — release a scoped kill switch after revalidation.

Release is never a blind ACTIVE → INACTIVE hop.  The switch first moves to
RELEASING and only returns to INACTIVE after the release preconditions pass:

    System = READY
    Risk = HEALTHY
    Execution = HEALTHY
    Event Bus = HEALTHY
    Position = TRUSTED
    Ledger = TRUSTED
    Recovery = NONE
    Market Data = FRESH

If any precondition fails the release is blocked and the switch stays ACTIVE
(spec section 36).  This command builds the release-precondition checks from
the supplied GateContext and forwards them into KillSwitch.release().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from ..domain.system_state import SystemState
from ..health.health_status import HealthStatus
from ..health.readiness import DataFreshness
from ..kill_switch.kill_switch import KillSwitch, KillSwitchRelease
from ..kill_switch.kill_switch_scope import KillSwitchScope
from ..trading_gate.gate_context import GateContext
from ..trading_gate.gate_reason import GateReason

#: Release precondition checks, in order (spec section 36).
RELEASE_PRECONDITIONS: List[Callable[[GateContext], Optional[GateReason]]] = [
    lambda ctx: None
    if ctx.system_state is SystemState.READY
    else GateReason.SYSTEM_NOT_READY,
    lambda ctx: None
    if ctx.risk_health is HealthStatus.HEALTHY
    else GateReason.RISK_ENGINE_UNHEALTHY,
    lambda ctx: None
    if ctx.execution_health is HealthStatus.HEALTHY
    else GateReason.EXECUTION_ENGINE_UNHEALTHY,
    lambda ctx: None
    if ctx.event_bus_health is HealthStatus.HEALTHY
    else GateReason.EVENT_BUS_UNHEALTHY,
    lambda ctx: None
    if ctx.position_health is not HealthStatus.UNHEALTHY
    else GateReason.POSITION_STATE_UNTRUSTED,
    lambda ctx: None
    if ctx.ledger_health is not HealthStatus.UNHEALTHY
    else GateReason.LEDGER_STATE_UNTRUSTED,
    lambda ctx: None
    if ctx.active_recovery is None or not ctx.active_recovery.is_active
    else GateReason.RECOVERY_IN_PROGRESS,
    lambda ctx: None
    if ctx.market_data_freshness is DataFreshness.FRESH
    else GateReason.MARKET_DATA_STALE,
]


def release_precondition_blocks(context: GateContext) -> List[GateReason]:
    """Return every release precondition that currently fails."""
    return [reason for check in RELEASE_PRECONDITIONS for reason in [check(context)] if reason]


@dataclass
class ReleaseKillSwitch:
    """Command: release a scoped kill switch with precondition revalidation."""

    scope: KillSwitchScope
    scope_id: Optional[str] = None
    actor: str = ""
    correlation_id: str = ""
    now: Optional[datetime] = None

    def execute(
        self,
        kill_switch: KillSwitch,
        context: Optional[GateContext] = None,
    ) -> KillSwitchRelease:
        if context is None:
            return kill_switch.request_release(
                self.scope, self.scope_id, self.actor, self.now
            )
        return kill_switch.release(
            self.scope,
            self.scope_id,
            self.actor,
            validate=lambda: release_precondition_blocks(context),
            now=self.now,
        )
