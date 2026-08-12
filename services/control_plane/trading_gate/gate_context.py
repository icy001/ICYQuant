"""
GateContext — the full snapshot of system state that the gate evaluates.

One context is built per order request and carries everything the policy
needs to answer "can this instruction proceed?":

    system_state        SystemState          e.g. READY
    trading_state       TradingState         e.g. TRADING_READY
    operational_state   OperationalState     e.g. NORMAL / EMERGENCY

    risk_health         HealthStatus         e.g. HEALTHY
    position_health     HealthStatus
    ledger_health       HealthStatus
    execution_health    HealthStatus
    event_bus_health    HealthStatus

    active_recovery     Optional[RecoveryState]
    kill_switch_state   KillSwitchState      e.g. INACTIVE / ACTIVE
    market_data_freshness DataFreshness      e.g. FRESH / STALE
    risk_decision       RiskDecision         e.g. APPROVED

    order               OrderContext         the instruction being gated
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from ..domain.operational_state import OperationalState
from ..domain.system_state import SystemState
from ..domain.trading_state import TradingState
from ..health.health_status import HealthStatus
from ..health.readiness import DataFreshness
from ..kill_switch.kill_switch_state import KillSwitchState
from ..recovery.recovery_state import RecoveryState


class RiskDecision(str, Enum):
    """Result of the Risk Engine for this instruction (double-authorisation)."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


@dataclass
class OrderContext:
    """The trading instruction being gated — used for scoped kill switches."""

    order_id: str = ""
    strategy_id: str = ""
    account_id: str = ""
    instrument_id: str = ""
    venue_id: str = ""
    order_flow_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "venue_id": self.venue_id,
            "order_flow_id": self.order_flow_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderContext":
        return cls(
            order_id=data.get("order_id", ""),
            strategy_id=data.get("strategy_id", ""),
            account_id=data.get("account_id", ""),
            instrument_id=data.get("instrument_id", ""),
            venue_id=data.get("venue_id", ""),
            order_flow_id=data.get("order_flow_id", ""),
        )


@dataclass
class GateContext:
    """Snapshot of the whole system relevant to one gate evaluation."""

    system_state: SystemState = SystemState.INITIALIZING
    trading_state: TradingState = TradingState.TRADING_DISABLED
    operational_state: OperationalState = OperationalState.NORMAL

    risk_health: HealthStatus = HealthStatus.UNKNOWN
    position_health: HealthStatus = HealthStatus.UNKNOWN
    ledger_health: HealthStatus = HealthStatus.UNKNOWN
    execution_health: HealthStatus = HealthStatus.UNKNOWN
    event_bus_health: HealthStatus = HealthStatus.UNKNOWN

    active_recovery: Optional[RecoveryState] = None
    kill_switch_state: KillSwitchState = KillSwitchState.INACTIVE
    market_data_freshness: DataFreshness = DataFreshness.UNKNOWN
    risk_decision: RiskDecision = RiskDecision.PENDING
    order: OrderContext = field(default_factory=OrderContext)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_state": self.system_state.value,
            "trading_state": self.trading_state.value,
            "operational_state": self.operational_state.value,
            "risk_health": self.risk_health.value,
            "position_health": self.position_health.value,
            "ledger_health": self.ledger_health.value,
            "execution_health": self.execution_health.value,
            "event_bus_health": self.event_bus_health.value,
            "active_recovery": self.active_recovery.value if self.active_recovery else None,
            "kill_switch_state": self.kill_switch_state.value,
            "market_data_freshness": self.market_data_freshness.value,
            "risk_decision": self.risk_decision.value,
            "order": self.order.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateContext":
        return cls(
            system_state=SystemState(data["system_state"]),
            trading_state=TradingState(data["trading_state"]),
            operational_state=OperationalState(data["operational_state"]),
            risk_health=HealthStatus(data["risk_health"]),
            position_health=HealthStatus(data["position_health"]),
            ledger_health=HealthStatus(data["ledger_health"]),
            execution_health=HealthStatus(data["execution_health"]),
            event_bus_health=HealthStatus(data["event_bus_health"]),
            active_recovery=RecoveryState(data["active_recovery"])
            if data.get("active_recovery")
            else None,
            kill_switch_state=KillSwitchState(data["kill_switch_state"]),
            market_data_freshness=DataFreshness(data["market_data_freshness"]),
            risk_decision=RiskDecision(data["risk_decision"]),
            order=OrderContext.from_dict(data.get("order", {})),
        )
