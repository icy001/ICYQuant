"""
PolicyContext — a deterministic snapshot of everything the Policy Engine needs.

Every evaluation receives exactly one context.  The same context must always
produce the same PolicyEvaluation (P(S) = same result) — no hidden ordering,
threading or network state may influence the outcome.

Fields are the union of:

    system_state, trading_state, operational_state
    risk / position / ledger / execution / event_bus health
    risk / position / ledger integrity
    market_data_freshness (+ stale duration)
    kill_switch_state (+ scope)
    recovery_state (+ progress)
    critical_unhealthy_components, consecutive_failures,
    consecutive_healthy_checks, active_incidents
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..domain.component_state import ComponentState
from ..domain.operational_state import OperationalState
from ..domain.system_state import SystemState
from ..domain.trading_gate import RiskIntegrity
from ..domain.trading_state import TradingState


class MarketDataFreshness(str, Enum):
    """Freshness of the market data feed."""

    FRESH = "FRESH"
    STALE = "STALE"
    CRITICAL = "CRITICAL"


class KillSwitchState(str, Enum):
    """Lifecycle state of the kill switch (mirrors 24.3 semantics)."""

    INACTIVE = "INACTIVE"
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    RELEASING = "RELEASING"


class RecoveryState(str, Enum):
    """Recovery pipeline state."""

    NONE = "NONE"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> Any:
    """Return the raw value of an Enum member (tolerant of plain strings)."""
    return value.value if isinstance(value, Enum) else value


@dataclass
class PolicyContext:
    """Immutable-in-spirit snapshot used for a single policy evaluation."""

    system_state: SystemState = SystemState.READY
    trading_state: TradingState = TradingState.TRADING_READY
    operational_state: OperationalState = OperationalState.NORMAL

    # component health
    component_states: Dict[str, ComponentState] = field(default_factory=dict)
    risk_health: ComponentState = ComponentState.HEALTHY
    position_health: ComponentState = ComponentState.HEALTHY
    ledger_health: ComponentState = ComponentState.HEALTHY
    execution_health: ComponentState = ComponentState.HEALTHY
    event_bus_health: ComponentState = ComponentState.HEALTHY

    # integrity
    risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    position_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    ledger_integrity: RiskIntegrity = RiskIntegrity.TRUSTED

    # market data
    market_data_freshness: MarketDataFreshness = MarketDataFreshness.FRESH
    market_data_stale_seconds: float = 0.0

    # kill switch
    kill_switch_state: KillSwitchState = KillSwitchState.INACTIVE
    kill_switch_scope: str = ""

    # recovery
    recovery_state: RecoveryState = RecoveryState.NONE
    recovery_progress: float = 0.0

    # aggregate signals
    critical_unhealthy_components: int = 0
    consecutive_failures: int = 0
    consecutive_healthy_checks: int = 0
    active_incidents: List[str] = field(default_factory=list)

    # traceability
    correlation_id: str = ""
    captured_at: Optional[datetime] = None

    # -- resolution -------------------------------------------------------

    def resolve(self, path: str) -> Any:
        """Resolve a dot-path (``"risk_health"``, ``"component_states.market_data"``)."""
        if not path:
            return None
        parts = path.split(".")
        head = parts[0]
        if not hasattr(self, head):
            return None
        value: Any = getattr(self, head)
        for part in parts[1:]:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    # -- helpers ----------------------------------------------------------

    @property
    def is_healthy(self) -> bool:
        """All trading-critical components are healthy and trusted."""
        return (
            self.risk_health is ComponentState.HEALTHY
            and self.execution_health is ComponentState.HEALTHY
            and self.event_bus_health is ComponentState.HEALTHY
            and self.position_health is ComponentState.HEALTHY
            and self.ledger_health is ComponentState.HEALTHY
            and self.risk_integrity is RiskIntegrity.TRUSTED
            and self.position_integrity is RiskIntegrity.TRUSTED
            and self.ledger_integrity is RiskIntegrity.TRUSTED
        )

    @property
    def market_data_is_fresh(self) -> bool:
        return self.market_data_freshness is MarketDataFreshness.FRESH

    # -- serialization ----------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Serialised context — stored verbatim in the audit trail."""
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_state": _enum_value(self.system_state),
            "trading_state": _enum_value(self.trading_state),
            "operational_state": _enum_value(self.operational_state),
            "component_states": {
                k: _enum_value(v) for k, v in self.component_states.items()
            },
            "risk_health": _enum_value(self.risk_health),
            "position_health": _enum_value(self.position_health),
            "ledger_health": _enum_value(self.ledger_health),
            "execution_health": _enum_value(self.execution_health),
            "event_bus_health": _enum_value(self.event_bus_health),
            "risk_integrity": _enum_value(self.risk_integrity),
            "position_integrity": _enum_value(self.position_integrity),
            "ledger_integrity": _enum_value(self.ledger_integrity),
            "market_data_freshness": _enum_value(self.market_data_freshness),
            "market_data_stale_seconds": self.market_data_stale_seconds,
            "kill_switch_state": _enum_value(self.kill_switch_state),
            "kill_switch_scope": self.kill_switch_scope,
            "recovery_state": _enum_value(self.recovery_state),
            "recovery_progress": self.recovery_progress,
            "critical_unhealthy_components": self.critical_unhealthy_components,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_healthy_checks": self.consecutive_healthy_checks,
            "active_incidents": list(self.active_incidents),
            "correlation_id": self.correlation_id,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyContext":
        captured = data.get("captured_at")
        captured_at = (
            datetime.fromisoformat(captured) if captured else None
        )
        return cls(
            system_state=SystemState(data["system_state"]),
            trading_state=TradingState(data["trading_state"]),
            operational_state=OperationalState(data["operational_state"]),
            component_states={
                k: ComponentState(v)
                for k, v in data.get("component_states", {}).items()
            },
            risk_health=ComponentState(data.get("risk_health", "HEALTHY")),
            position_health=ComponentState(data.get("position_health", "HEALTHY")),
            ledger_health=ComponentState(data.get("ledger_health", "HEALTHY")),
            execution_health=ComponentState(data.get("execution_health", "HEALTHY")),
            event_bus_health=ComponentState(data.get("event_bus_health", "HEALTHY")),
            risk_integrity=RiskIntegrity(data.get("risk_integrity", "TRUSTED")),
            position_integrity=RiskIntegrity(data.get("position_integrity", "TRUSTED")),
            ledger_integrity=RiskIntegrity(data.get("ledger_integrity", "TRUSTED")),
            market_data_freshness=MarketDataFreshness(
                data.get("market_data_freshness", "FRESH")
            ),
            market_data_stale_seconds=data.get("market_data_stale_seconds", 0.0),
            kill_switch_state=KillSwitchState(
                data.get("kill_switch_state", "INACTIVE")
            ),
            kill_switch_scope=data.get("kill_switch_scope", ""),
            recovery_state=RecoveryState(data.get("recovery_state", "NONE")),
            recovery_progress=data.get("recovery_progress", 0.0),
            critical_unhealthy_components=data.get(
                "critical_unhealthy_components", 0
            ),
            consecutive_failures=data.get("consecutive_failures", 0),
            consecutive_healthy_checks=data.get("consecutive_healthy_checks", 0),
            active_incidents=list(data.get("active_incidents", [])),
            correlation_id=data.get("correlation_id", ""),
            captured_at=captured_at,
        )
