"""
RecoveryContext — a self-contained, traceable recovery session descriptor.

Every recovery run creates exactly one context.  The context captures *why*
the recovery started (incident, trigger), *where* it applies (scope + affected
entities) and *what* the world looked like at that moment (system / trading /
risk / position / ledger states).

A context is immutable-in-spirit: it is snapshotted once at start and then
replayed, audited and correlated through the whole recovery lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..domain.component_state import ComponentState
from ..domain.system_state import SystemState
from ..domain.trading_state import TradingState


class RecoveryScope(str, Enum):
    """Recovery blast radius — keeps a failure localised when policy allows."""

    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    STRATEGY = "STRATEGY"
    INSTRUMENT = "INSTRUMENT"
    SERVICE = "SERVICE"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> Any:
    """Raw value of an Enum member (tolerant of plain strings)."""
    return value.value if isinstance(value, Enum) else value


@dataclass
class RecoveryContext:
    """Snapshot of the world at recovery start."""

    recovery_id: str = ""
    incident_id: str = ""
    trigger: str = ""
    scope: RecoveryScope = RecoveryScope.SERVICE
    affected_services: List[str] = field(default_factory=list)
    affected_accounts: List[str] = field(default_factory=list)
    affected_strategies: List[str] = field(default_factory=list)
    affected_instruments: List[str] = field(default_factory=list)

    # world state at detection time
    system_state: SystemState = SystemState.DEGRADED
    trading_state: TradingState = TradingState.TRADING_READY
    risk_state: ComponentState = ComponentState.HEALTHY
    position_state: ComponentState = ComponentState.HEALTHY
    ledger_state: ComponentState = ComponentState.HEALTHY

    # timing / governance
    started_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    attempt: int = 1
    policy_version: str = ""
    correlation_id: str = ""

    # runtime: outputs produced by completed steps (shared across the plan,
    # serialised so a crashed orchestrator can resume with full context)
    step_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = _utcnow()

    # -- helpers ----------------------------------------------------------

    def with_recovery_id(self, recovery_id: str) -> "RecoveryContext":
        self.recovery_id = recovery_id
        return self

    @property
    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Whether the recovery deadline has passed."""
        if self.deadline is None:
            return False
        return (now or _utcnow()) > self.deadline

    # -- serialization ----------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "incident_id": self.incident_id,
            "trigger": self.trigger,
            "scope": _enum_value(self.scope),
            "affected_services": list(self.affected_services),
            "affected_accounts": list(self.affected_accounts),
            "affected_strategies": list(self.affected_strategies),
            "affected_instruments": list(self.affected_instruments),
            "system_state": _enum_value(self.system_state),
            "trading_state": _enum_value(self.trading_state),
            "risk_state": _enum_value(self.risk_state),
            "position_state": _enum_value(self.position_state),
            "ledger_state": _enum_value(self.ledger_state),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "attempt": self.attempt,
            "policy_version": self.policy_version,
            "correlation_id": self.correlation_id,
            "step_outputs": {
                k: dict(v) for k, v in self.step_outputs.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryContext":
        started = data.get("started_at")
        deadline = data.get("deadline")
        return cls(
            recovery_id=data.get("recovery_id", ""),
            incident_id=data.get("incident_id", ""),
            trigger=data.get("trigger", ""),
            scope=RecoveryScope(data.get("scope", "SERVICE")),
            affected_services=list(data.get("affected_services", [])),
            affected_accounts=list(data.get("affected_accounts", [])),
            affected_strategies=list(data.get("affected_strategies", [])),
            affected_instruments=list(data.get("affected_instruments", [])),
            system_state=SystemState(data.get("system_state", "DEGRADED")),
            trading_state=TradingState(data.get("trading_state", "TRADING_READY")),
            risk_state=ComponentState(data.get("risk_state", "HEALTHY")),
            position_state=ComponentState(data.get("position_state", "HEALTHY")),
            ledger_state=ComponentState(data.get("ledger_state", "HEALTHY")),
            started_at=datetime.fromisoformat(started) if started else None,
            deadline=datetime.fromisoformat(deadline) if deadline else None,
            attempt=data.get("attempt", 1),
            policy_version=data.get("policy_version", ""),
            correlation_id=data.get("correlation_id", ""),
            step_outputs={
                k: dict(v) for k, v in data.get("step_outputs", {}).items()
            },
        )


__all__ = ["RecoveryScope", "RecoveryContext"]
