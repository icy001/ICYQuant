"""
ControlPlaneSnapshot — the current operational view of the system.

A snapshot is a *projection*, NOT a source of truth:

    Snapshot = Current Operational View (derived)
    Events   = Business Facts            (source of truth)

If the snapshot is lost or corrupted it can always be rebuilt by replaying the
control-plane event log (see ControlPlaneService.rebuild_snapshot).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .operational_state import OperationalState
from .system_state import StateReasonCode, SystemState
from .trading_gate import RiskIntegrity, TradingGateResult
from .trading_state import TradingState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ControlPlaneSnapshot:
    """Operational snapshot exposed to UI / API / Alerting."""

    system_state: SystemState
    trading_state: TradingState
    operational_state: OperationalState
    component_states: Dict[str, str] = field(default_factory=dict)
    component_health: Dict[str, float] = field(default_factory=dict)
    active_recoveries: List[str] = field(default_factory=list)
    consistency_status: Optional[str] = None
    risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    trading_gate: Optional[TradingGateResult] = None
    snapshot_id: str = ""
    reason: Optional[StateReasonCode] = None
    generated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            self.snapshot_id = f"SNAP-{uuid.uuid4().hex[:12].upper()}"
        if self.generated_at is None:
            self.generated_at = _utcnow()

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "system_state": self.system_state.value,
            "trading_state": self.trading_state.value,
            "operational_state": self.operational_state.value,
            "component_states": dict(self.component_states),
            "component_health": dict(self.component_health),
            "active_recoveries": list(self.active_recoveries),
            "consistency_status": self.consistency_status,
            "risk_integrity": self.risk_integrity.value,
            "trading_gate": self.trading_gate.to_dict()
            if self.trading_gate is not None
            else None,
            "reason": self.reason.value if self.reason is not None else None,
            "generated_at": self.generated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlPlaneSnapshot":
        gate = data.get("trading_gate")
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            system_state=SystemState(data["system_state"]),
            trading_state=TradingState(data["trading_state"]),
            operational_state=OperationalState(data["operational_state"]),
            component_states=dict(data.get("component_states", {})),
            component_health={k: float(v) for k, v in data.get("component_health", {}).items()},
            active_recoveries=list(data.get("active_recoveries", [])),
            consistency_status=data.get("consistency_status"),
            risk_integrity=RiskIntegrity(data["risk_integrity"]),
            trading_gate=TradingGateResult.from_dict(gate) if gate is not None else None,
            reason=StateReasonCode(data["reason"]) if data.get("reason") else None,
            generated_at=datetime.fromisoformat(data["generated_at"])
            if data.get("generated_at")
            else None,
        )
