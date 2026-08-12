"""
ActivateKillSwitch — activate a scoped kill switch (manual or automatic).

Activation is high-risk and therefore requires:

    scope   — GLOBAL / ACCOUNT / STRATEGY / INSTRUMENT / VENUE / ORDER_FLOW
    reason  — why (KillSwitchReason)
    actor   — who (operator id or "auto-kill-policy")

Repeated activation of an already-ACTIVE switch is idempotent
(ALREADY_ACTIVE) so concurrent automatic triggers deduplicate into a single
ACTIVE switch (spec section 47).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..events.kill_switch_activated import KillSwitchActivated
from ..kill_switch.kill_switch import (
    KillSwitch,
    KillSwitchActivation,
    KillSwitchActivationOutcome,
)
from ..kill_switch.kill_switch_reason import KillSwitchReason
from ..kill_switch.kill_switch_scope import KillSwitchScope


@dataclass
class ActivateKillSwitch:
    """Command: activate a scoped kill switch."""

    scope: KillSwitchScope
    reason: KillSwitchReason
    actor: str
    scope_id: Optional[str] = None
    correlation_id: str = ""
    now: Optional[datetime] = None

    def execute(self, kill_switch: KillSwitch) -> KillSwitchActivation:
        return kill_switch.activate(
            scope=self.scope,
            scope_id=self.scope_id,
            reason=self.reason,
            actor=self.actor,
            correlation_id=self.correlation_id,
            now=self.now,
        )


def make_kill_switch_activated_event(
    activation: KillSwitchActivation,
) -> Optional[KillSwitchActivated]:
    """Return the KILL_SWITCH_ACTIVATED event (None when already active)."""
    if activation.outcome is not KillSwitchActivationOutcome.ACTIVATED:
        return None
    return activation.event
