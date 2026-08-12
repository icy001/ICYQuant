"""
KillSwitch — the highest-priority trading halt mechanism.

A Kill Switch is *not* an ordinary Trading Gate rule: it is a hard gate that
sits *above* the Trading Gate (priority 0).  When a matching switch is ACTIVE
every new trading instruction in its scope is DENY — no exceptions, even when
Risk = APPROVED and the system is otherwise READY.

Scoping (spec section 15):

    GLOBAL / ACCOUNT / STRATEGY / INSTRUMENT / VENUE / ORDER_FLOW

Priority (spec section 21):

    GLOBAL > ACCOUNT > STRATEGY > INSTRUMENT > VENUE

Idempotency:

    activate() on an already-ACTIVE switch  → ALREADY_ACTIVE (no re-activation)
    release()  on an already-INACTIVE switch → ALREADY_RELEASED

Release is a two-phase flow (spec section 34):

    ACTIVE → RELEASING → (preconditions revalidated) → INACTIVE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..health.health_status import HealthStatus
from ..trading_gate.gate_context import OrderContext
from ..trading_gate.gate_reason import GateReason
from .kill_switch_reason import KillSwitchReason
from .kill_switch_scope import KILL_SWITCH_PRIORITY, KillSwitchScope
from .kill_switch_state import KillSwitchState


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class KillSwitchActivationOutcome(str, Enum):
    ACTIVATED = "ACTIVATED"
    ALREADY_ACTIVE = "ALREADY_ACTIVE"


class KillSwitchReleaseOutcome(str, Enum):
    RELEASED = "RELEASED"
    ALREADY_RELEASED = "ALREADY_RELEASED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    RELEASE_BLOCKED = "RELEASE_BLOCKED"


@dataclass
class KillSwitchEntry:
    """One scoped kill switch and its lifecycle."""

    scope: KillSwitchScope
    reason: KillSwitchReason
    actor: str
    scope_id: Optional[str] = None
    state: KillSwitchState = KillSwitchState.INACTIVE
    correlation_id: str = ""
    activated_at: Optional[datetime] = None
    release_requested_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    activation_count: int = 0

    @property
    def key(self) -> Tuple[KillSwitchScope, Optional[str]]:
        return (self.scope, self.scope_id)

    @property
    def is_blocking(self) -> bool:
        return self.state.is_blocking

    def matches(self, order: OrderContext) -> bool:
        """Does this switch apply to the given instruction?"""
        if self.scope is KillSwitchScope.GLOBAL:
            return True
        if self.scope is KillSwitchScope.ACCOUNT:
            return order.account_id == self.scope_id
        if self.scope is KillSwitchScope.STRATEGY:
            return order.strategy_id == self.scope_id
        if self.scope is KillSwitchScope.INSTRUMENT:
            return order.instrument_id == self.scope_id
        if self.scope is KillSwitchScope.VENUE:
            return order.venue_id == self.scope_id
        if self.scope is KillSwitchScope.ORDER_FLOW:
            return order.order_flow_id == self.scope_id
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "state": self.state.value,
            "reason": self.reason.value,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "release_requested_at": self.release_requested_at.isoformat()
            if self.release_requested_at
            else None,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "activation_count": self.activation_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KillSwitchEntry":
        def _dt(value: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(value) if value else None

        return cls(
            scope=KillSwitchScope(data["scope"]),
            scope_id=data.get("scope_id"),
            state=KillSwitchState(data["state"]),
            reason=KillSwitchReason(data["reason"]),
            actor=data["actor"],
            correlation_id=data.get("correlation_id", ""),
            activated_at=_dt(data.get("activated_at")),
            release_requested_at=_dt(data.get("release_requested_at")),
            released_at=_dt(data.get("released_at")),
            activation_count=int(data.get("activation_count", 0)),
        )


@dataclass
class KillSwitchActivation:
    """Result of activating a kill switch."""

    outcome: KillSwitchActivationOutcome
    entry: KillSwitchEntry
    event: Optional[Any] = None


@dataclass
class KillSwitchRelease:
    """Result of releasing a kill switch."""

    outcome: KillSwitchReleaseOutcome
    entry: KillSwitchEntry
    blocked_reasons: List[GateReason] = field(default_factory=list)
    event: Optional[Any] = None


class KillSwitch:
    """In-memory registry of scoped kill switches."""

    def __init__(self) -> None:
        self._entries: Dict[Tuple[KillSwitchScope, Optional[str]], KillSwitchEntry] = {}

    # ------------------------------------------------------------------
    # activation
    # ------------------------------------------------------------------

    def activate(
        self,
        scope: KillSwitchScope,
        reason: KillSwitchReason,
        actor: str,
        scope_id: Optional[str] = None,
        correlation_id: str = "",
        now: Optional[datetime] = None,
    ) -> KillSwitchActivation:
        """
        Activate a scoped kill switch.

        Activation is high-risk: reason, actor and scope are required
        (spec section 44).  Repeated activation of an already-ACTIVE switch
        is idempotent — it returns ALREADY_ACTIVE and never re-arms the switch.
        """
        self._validate_activation(scope, scope_id, reason, actor)
        scope = KillSwitchScope(scope)
        reason = KillSwitchReason(reason)
        now = now or _utcnow()

        key = (scope, scope_id)
        entry = self._entries.get(key)

        if entry is not None and entry.state is KillSwitchState.ACTIVE:
            entry.activation_count += 1
            return KillSwitchActivation(
                KillSwitchActivationOutcome.ALREADY_ACTIVE, entry
            )

        if entry is None:
            entry = KillSwitchEntry(
                scope=scope,
                scope_id=scope_id,
                state=KillSwitchState.ACTIVE,
                reason=reason,
                actor=actor,
                correlation_id=correlation_id,
                activated_at=now,
                activation_count=1,
            )
            self._entries[key] = entry
        else:
            # ARMED / RELEASING / INACTIVE re-activation re-arms the switch.
            entry.state = KillSwitchState.ACTIVE
            entry.reason = reason
            entry.actor = actor
            entry.correlation_id = correlation_id
            entry.activated_at = now
            entry.released_at = None
            entry.release_requested_at = None
            entry.activation_count += 1

        from ..events.kill_switch_activated import KillSwitchActivated

        event = KillSwitchActivated(
            scope=scope,
            scope_id=scope_id,
            reason=reason,
            actor=actor,
            correlation_id=correlation_id,
            activated_at=now,
        )
        return KillSwitchActivation(KillSwitchActivationOutcome.ACTIVATED, entry, event)

    def _validate_activation(
        self,
        scope: KillSwitchScope,
        scope_id: Optional[str],
        reason: KillSwitchReason,
        actor: str,
    ) -> None:
        if scope is None:
            raise ValueError("kill switch activation requires a scope")
        if reason is None:
            raise ValueError("kill switch activation requires a reason")
        if not actor:
            raise ValueError("kill switch activation requires an actor")
        if scope is KillSwitchScope.GLOBAL and scope_id not in (None, ""):
            raise ValueError("GLOBAL kill switch must not carry a scope_id")
        if scope is not KillSwitchScope.GLOBAL and not scope_id:
            raise ValueError(f"{scope.value} kill switch requires a scope_id")

    # ------------------------------------------------------------------
    # release
    # ------------------------------------------------------------------

    def request_release(
        self,
        scope: KillSwitchScope,
        scope_id: Optional[str] = None,
        actor: str = "",
        now: Optional[datetime] = None,
    ) -> KillSwitchRelease:
        """ACTIVE → RELEASING. Release stays blocked until revalidated."""
        entry = self.get(scope, scope_id)
        if entry is None or entry.state is KillSwitchState.INACTIVE:
            if entry is None:
                entry = self._make_entry(scope, scope_id)
            return KillSwitchRelease(KillSwitchReleaseOutcome.ALREADY_RELEASED, entry)
        if entry.state is KillSwitchState.RELEASING:
            return KillSwitchRelease(KillSwitchReleaseOutcome.RELEASE_REQUESTED, entry)
        now = now or _utcnow()
        entry.state = KillSwitchState.RELEASING
        entry.release_requested_at = now
        return KillSwitchRelease(KillSwitchReleaseOutcome.RELEASE_REQUESTED, entry)

    def complete_release(
        self,
        scope: KillSwitchScope,
        scope_id: Optional[str] = None,
        actor: str = "",
        now: Optional[datetime] = None,
    ) -> KillSwitchRelease:
        """RELEASING → INACTIVE. Only after the preconditions were revalidated."""
        entry = self.get(scope, scope_id)
        if entry is None or entry.state is KillSwitchState.INACTIVE:
            if entry is None:
                entry = self._make_entry(scope, scope_id)
            return KillSwitchRelease(KillSwitchReleaseOutcome.ALREADY_RELEASED, entry)
        if entry.state is not KillSwitchState.RELEASING:
            return KillSwitchRelease(KillSwitchReleaseOutcome.RELEASE_BLOCKED, entry)
        now = now or _utcnow()
        entry.state = KillSwitchState.INACTIVE
        entry.released_at = now
        return KillSwitchRelease(KillSwitchReleaseOutcome.RELEASED, entry)

    def release(
        self,
        scope: KillSwitchScope,
        scope_id: Optional[str] = None,
        actor: str = "",
        validate: Optional[Callable[[], List[GateReason]]] = None,
        now: Optional[datetime] = None,
    ) -> KillSwitchRelease:
        """
        Full release: ACTIVE → RELEASING → revalidate → INACTIVE.

        ``validate`` returns the list of blocking GateReasons (empty = safe).
        If any precondition fails, the switch stays ACTIVE and the outcome is
        RELEASE_BLOCKED (spec section 36).
        """
        entry = self.get(scope, scope_id)
        if entry is None or entry.state is KillSwitchState.INACTIVE:
            if entry is None:
                entry = self._make_entry(scope, scope_id)
            return KillSwitchRelease(KillSwitchReleaseOutcome.ALREADY_RELEASED, entry)

        blockers: List[GateReason] = list(validate() if validate else [])
        if blockers:
            return KillSwitchRelease(
                KillSwitchReleaseOutcome.RELEASE_BLOCKED, entry, blockers
            )

        self.request_release(scope, scope_id, actor, now)
        result = self.complete_release(scope, scope_id, actor, now)
        if result.outcome is KillSwitchReleaseOutcome.RELEASED:
            from ..events.kill_switch_released import KillSwitchReleased

            result.event = KillSwitchReleased(
                scope=entry.scope,
                scope_id=entry.scope_id,
                actor=actor or entry.actor,
                reason=entry.reason,
                correlation_id=entry.correlation_id,
                released_at=entry.released_at or now or _utcnow(),
            )
        return result

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def get(self, scope: KillSwitchScope, scope_id: Optional[str] = None) -> Optional[KillSwitchEntry]:
        return self._entries.get((scope, scope_id))

    def has_active(self, scope: KillSwitchScope, scope_id: Optional[str] = None) -> bool:
        entry = self.get(scope, scope_id)
        return entry is not None and entry.state is KillSwitchState.ACTIVE

    def is_blocked(self, order: OrderContext) -> Optional[KillSwitchEntry]:
        """Highest-priority matching switch in a blocking state, or None."""
        for scope in KILL_SWITCH_PRIORITY:
            for entry in self._entries.values():
                if entry.scope is not scope:
                    continue
                if not entry.is_blocking:
                    continue
                if entry.matches(order):
                    return entry
        return None

    def list_active(self) -> List[KillSwitchEntry]:
        return [e for e in self._entries.values() if e.is_blocking]

    def list_all(self) -> List[KillSwitchEntry]:
        return list(self._entries.values())

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def _make_entry(self, scope: KillSwitchScope, scope_id: Optional[str]) -> KillSwitchEntry:
        entry = KillSwitchEntry(
            scope=scope,
            scope_id=scope_id,
            reason=KillSwitchReason.OPERATOR_ACTION,
            actor="system",
            state=KillSwitchState.INACTIVE,
        )
        self._entries[(scope, scope_id)] = entry
        return entry

    # ------------------------------------------------------------------
    # automatic activation (spec sections 38-39)
    # ------------------------------------------------------------------

    def auto_activate(
        self,
        component_health: Optional[Dict[str, HealthStatus]] = None,
        position_integrity_ok: bool = True,
        reconciliation_ok: bool = True,
        correlation_id: str = "",
        now: Optional[datetime] = None,
    ) -> Optional[KillSwitchActivation]:
        """
        Evaluate the automatic kill conditions and, if any critical condition
        fails, activate a GLOBAL kill switch (deduplicated).

        Conditions (spec section 39):

            risk engine critical failure          → RISK_SYSTEM_FAILURE
            event bus critical failure            → EVENT_BUS_CRITICAL_FAILURE
            execution engine critical failure     → EXECUTION_ENGINE_CRITICAL_FAILURE
            position integrity failure            → POSITION_INTEGRITY_FAILURE
            global reconciliation failure         → RECONCILIATION_FAILURE

        Returns None when no condition triggers.
        """
        component_health = component_health or {}

        if component_health.get("risk_engine") is HealthStatus.UNHEALTHY:
            reason = KillSwitchReason.RISK_SYSTEM_FAILURE
        elif component_health.get("event_bus") is HealthStatus.UNHEALTHY:
            reason = KillSwitchReason.EVENT_BUS_CRITICAL_FAILURE
        elif component_health.get("execution_engine") is HealthStatus.UNHEALTHY:
            reason = KillSwitchReason.EXECUTION_ENGINE_CRITICAL_FAILURE
        elif not position_integrity_ok:
            reason = KillSwitchReason.POSITION_INTEGRITY_FAILURE
        elif not reconciliation_ok:
            reason = KillSwitchReason.RECONCILIATION_FAILURE
        else:
            return None

        return self.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=reason,
            actor="auto-kill-policy",
            correlation_id=correlation_id,
            now=now,
        )
