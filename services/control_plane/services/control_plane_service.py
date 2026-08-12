"""
ControlPlaneService — the production control layer for ICYQuant.

Responsibilities:
    * Component registration, heartbeat, heartbeat-timeout detection
    * Periodic evaluate(): Component + Consistency + Recovery + Risk → StateDecision
    * System / Trading / Operational state machines (transition validation)
    * Manual / Emergency halt, maintenance windows, restart cycles
    * Trading Gate (ALLOW / DENY) consumed by order flow and kill switches
    * ControlPlaneSnapshot projection + rebuild from the event log
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..commands.evaluate_trading_state import (
    EvaluateTradingState,
    EvaluateTradingStateResult,
)
from ..commands.update_component_state import (
    UpdateComponentState,
    UpdateComponentStateResult,
)
from ..domain.component_registry import (
    DEFAULT_COMPONENT_TYPES,
    ComponentInfo,
    ComponentRegistry,
    ComponentType,
)
from ..domain.component_state import ComponentState
from ..domain.control_policy import TradingPolicy
from ..domain.control_plane_snapshot import ControlPlaneSnapshot
from ..domain.operational_state import OperationalState
from ..domain.system_state import (
    StateReasonCode,
    StateTransitionError,
    SystemState,
    SystemStateMachine,
)
from ..domain.trading_gate import (
    GateDecision,
    RiskIntegrity,
    TradingGate,
    TradingGateResult,
)
from ..domain.trading_state import TradingState, TradingStateMachine
from ..events.component_state_changed import ComponentStateChanged
from ..events.system_state_changed import SystemStateChanged
from ..events.trading_state_changed import TradingStateChanged
from ..repositories.control_plane_repository import ControlPlaneRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ControlPlaneService:
    """Orchestrates the Control Plane state model."""

    repository: ControlPlaneRepository = field(default_factory=ControlPlaneRepository)
    heartbeat_timeout_ms: int = 15000
    """Default 15s — a component not heartbeating for this long becomes UNKNOWN."""

    # -- runtime state -----------------------------------------------------

    _registry: ComponentRegistry = field(default_factory=ComponentRegistry, repr=False)
    _system_state: SystemState = SystemState.INITIALIZING
    _trading_state: TradingState = TradingState.TRADING_DISABLED
    _operational_state: OperationalState = OperationalState.NORMAL
    _gate_result: Optional[TradingGateResult] = None

    _consistency_status: Optional[str] = None
    _recovery_active: bool = False
    _active_recoveries: List[str] = field(default_factory=list)
    _risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    _manual_halt: bool = False
    _emergency: bool = False

    _policy: TradingPolicy = field(default_factory=TradingPolicy, repr=False)
    _gate: TradingGate = field(default_factory=TradingGate, repr=False)
    _pending_events: List[Any] = field(default_factory=list, repr=False)

    # ======================================================================
    # Lifecycle
    # ======================================================================

    def start(self) -> None:
        """INITIALIZING → STARTING."""
        if self._system_state is not SystemState.INITIALIZING:
            raise StateTransitionError(self._system_state, SystemState.STARTING)
        self._apply_system_transition(
            SystemState.STARTING, StateReasonCode.SYSTEM_STARTING
        )
        self._save_snapshot()

    def complete_startup(self) -> None:
        """STARTING → READY.  Requires every trading-critical component to be healthy."""
        if self._system_state is not SystemState.STARTING:
            raise StateTransitionError(self._system_state, SystemState.READY)
        gate_result = self._gate.evaluate(
            self._registry.states(), self._risk_integrity
        )
        if gate_result.decision is not GateDecision.ALLOW:
            raise RuntimeError(
                f"Cannot complete startup: trading gate DENY ({gate_result.reason.value})"
            )
        self._apply_system_transition(
            SystemState.READY, StateReasonCode.STARTUP_COMPLETE
        )
        self._evaluate_and_persist()

    def restart(self) -> None:
        """HALTED / FAILED → STARTING (restart cycle)."""
        if self._system_state not in (SystemState.HALTED, SystemState.FAILED):
            raise StateTransitionError(self._system_state, SystemState.STARTING)
        self._apply_system_transition(
            SystemState.STARTING, StateReasonCode.RESTART_REQUESTED
        )
        self._save_snapshot()

    def fail(self, reason: StateReasonCode = StateReasonCode.COMPONENT_FAILED) -> None:
        """ANY → FAILED.  Trading is halted; the system must be restarted."""
        if self._system_state is not SystemState.FAILED:
            self._apply_system_transition(SystemState.FAILED, reason)
        self._evaluate_and_persist()

    def enter_maintenance(self, reason: StateReasonCode = StateReasonCode.MAINTENANCE) -> None:
        """READY → MAINTENANCE (trading suspended, system still monitored)."""
        if self._system_state is not SystemState.READY:
            raise StateTransitionError(self._system_state, SystemState.MAINTENANCE)
        self._apply_system_transition(SystemState.MAINTENANCE, reason)
        self._evaluate_and_persist()

    def exit_maintenance(self, reason: StateReasonCode = StateReasonCode.RESUME_REQUESTED) -> None:
        """MAINTENANCE → READY and re-evaluate trading."""
        if self._system_state is not SystemState.MAINTENANCE:
            raise StateTransitionError(self._system_state, SystemState.READY)
        self._apply_system_transition(SystemState.READY, reason)
        self._evaluate_and_persist()

    # ======================================================================
    # Component management
    # ======================================================================

    def register_component(
        self,
        component_id: str,
        component_type: ComponentType,
        version: str = "1.0.0",
    ) -> ComponentInfo:
        info = self._registry.register(
            component_id=component_id,
            component_type=component_type,
            version=version,
        )
        self.repository.save_component(info)
        return info

    def register_default_components(self, version: str = "1.0.0") -> int:
        """Register the standard component set; returns how many were registered."""
        for component_type in DEFAULT_COMPONENT_TYPES:
            self.register_component(
                component_id=component_type.value,
                component_type=component_type,
                version=version,
            )
        return self._registry.component_count()

    def update_component_state(
        self,
        component_id: str,
        new_state: ComponentState,
        reason: StateReasonCode,
        detail: str = "",
    ) -> UpdateComponentStateResult:
        """Apply a component state change, emit COMPONENT_STATE_CHANGED, re-evaluate."""
        command = UpdateComponentState(
            component_id=component_id,
            new_state=new_state,
            reason=reason,
            detail=detail,
        )
        result = command.execute(self._registry)
        if result.changed:
            self._emit(result.event)
            info = self._registry.get(component_id)
            if info is not None:
                self.repository.save_component(info)
            self._evaluate_and_persist()
        return result

    def set_health_score(self, component_id: str, score: float) -> None:
        info = self._registry.get(component_id)
        if info is None:
            raise ValueError(f"Unknown component '{component_id}' — register it first")
        info.set_health_score(score)
        self.repository.save_component(info)

    def heartbeat(self, component_id: str, at: Optional[datetime] = None) -> ComponentInfo:
        """Record a HEARTBEAT; an UNKNOWN component is restored to HEALTHY."""
        info = self._registry.get(component_id)
        if info is None:
            raise ValueError(f"Unknown component '{component_id}' — register it first")
        at = at or _utcnow()
        previous = info.state
        info.mark_heartbeat(at)
        if previous is ComponentState.UNKNOWN:
            self.update_component_state(
                component_id,
                ComponentState.HEALTHY,
                StateReasonCode.HEARTBEAT_RESTORED,
            )
        else:
            self.repository.save_component(info)
        return info

    def check_heartbeats(self, at: Optional[datetime] = None) -> List[str]:
        """
        Mark components with stale heartbeats as UNKNOWN and re-evaluate.

        Returns the list of component ids that just timed out.
        """
        at = at or _utcnow()
        timed_out = self._registry.apply_heartbeat_timeout(at, self.heartbeat_timeout_ms)
        for component_id, previous in timed_out:
            info = self._registry.get(component_id)
            if info is None:
                continue
            event = ComponentStateChanged.from_change(
                component_id=component_id,
                component_type=info.component_type,
                previous_state=previous,
                new_state=ComponentState.UNKNOWN,
                reason=StateReasonCode.HEARTBEAT_TIMEOUT,
                occurred_at=at,
            )
            self._emit(event)
            self.repository.save_component(info)
        if timed_out:
            self._evaluate_and_persist()
        return [component_id for component_id, _ in timed_out]

    # ======================================================================
    # Evaluation inputs
    # ======================================================================

    def set_consistency_status(self, status: Optional[str]) -> None:
        self._consistency_status = status

    def set_recovery_active(self, active: bool) -> None:
        self._recovery_active = bool(active)
        if not active:
            self._active_recoveries.clear()

    def set_risk_integrity(self, integrity: RiskIntegrity) -> None:
        self._risk_integrity = integrity

    def add_recovery(self, recovery_id: str) -> None:
        if recovery_id not in self._active_recoveries:
            self._active_recoveries.append(recovery_id)
        self._recovery_active = True

    def clear_recovery(self, recovery_id: str) -> None:
        if recovery_id in self._active_recoveries:
            self._active_recoveries.remove(recovery_id)
        self._recovery_active = bool(self._active_recoveries)

    # ======================================================================
    # Control actions
    # ======================================================================

    def manual_halt(self, reason: StateReasonCode = StateReasonCode.MANUAL_HALT) -> None:
        """Freeze trading while the system keeps running (monitoring/recovery)."""
        self._manual_halt = True
        self._evaluate_and_persist()

    def resume(self, reason: StateReasonCode = StateReasonCode.RESUME_REQUESTED) -> None:
        """Lift a manual halt and re-evaluate trading."""
        self._manual_halt = False
        self._evaluate_and_persist()

    def emergency_halt(self, reason: StateReasonCode = StateReasonCode.EMERGENCY_HALT) -> None:
        """Emergency: halt trading and enter EMERGENCY operational mode."""
        self._emergency = True
        self._evaluate_and_persist()

    def clear_emergency(self) -> None:
        """Clear the emergency flag; the system follows the restart cycle."""
        self._emergency = False
        self._evaluate_and_persist()

    # ======================================================================
    # Evaluation
    # ======================================================================

    def evaluate(
        self,
        consistency_status: Optional[str] = None,
        recovery_active: Optional[bool] = None,
        risk_integrity: Optional[RiskIntegrity] = None,
    ) -> EvaluateTradingStateResult:
        """
        Recompute System / Trading / Operational state from component states,
        consistency, recovery and risk-integrity inputs.

        State changes are emitted as events; the snapshot is refreshed.
        """
        if consistency_status is not None:
            self._consistency_status = consistency_status
        if recovery_active is not None:
            self._recovery_active = recovery_active
        if risk_integrity is not None:
            self._risk_integrity = risk_integrity

        result = EvaluateTradingState(
            current_system_state=self._system_state,
            current_trading_state=self._trading_state,
            current_operational_state=self._operational_state,
            policy=self._policy,
            gate=self._gate,
            consistency_status=self._consistency_status,
            recovery_active=self._recovery_active,
            risk_integrity=self._risk_integrity,
            manual_halt=self._manual_halt,
            emergency=self._emergency,
        ).execute(self._registry)

        if result.system_state is not self._system_state:
            self._apply_system_transition(
                result.system_state, result.decision.reason, result.decision.source
            )
        if result.trading_state is not self._trading_state:
            self._apply_trading_transition(
                result.trading_state,
                result.decision.reason,
                result.gate_result.decision.value,
            )
        self._operational_state = result.operational_state
        self._gate_result = result.gate_result
        self._save_snapshot()
        return result

    def can_trade(self) -> bool:
        """
        Can trading proceed right now?

        Based on the Trading State (not just the gate) so that manual / emergency
        halts correctly freeze order flow even when components are healthy.
        """
        return self._trading_state in (
            TradingState.TRADING_READY,
            TradingState.TRADING_DEGRADED,
        )

    # ======================================================================
    # API contract
    # ======================================================================

    def get_state(self) -> Dict[str, str]:
        """GET /control-plane/state contract."""
        return {
            "system": self._system_state.value,
            "trading": self._trading_state.value,
            "operational": self._operational_state.value,
        }

    def get_components(self) -> List[Dict[str, Any]]:
        """GET /control-plane/components contract."""
        return [info.to_dict() for info in self._registry.list_components()]

    def get_trading_gate(self) -> Dict[str, str]:
        """GET /control-plane/trading-gate contract."""
        gate_result = self._gate_result
        if gate_result is None:
            gate_result = self._gate.evaluate(
                self._registry.states(), self._risk_integrity
            )
        return {"decision": gate_result.decision.value, "reason": gate_result.reason.value}

    # ======================================================================
    # Snapshot
    # ======================================================================

    def build_snapshot(self) -> ControlPlaneSnapshot:
        gate_result = self._gate_result
        if gate_result is None:
            gate_result = self._gate.evaluate(
                self._registry.states(), self._risk_integrity
            )
        return ControlPlaneSnapshot(
            system_state=self._system_state,
            trading_state=self._trading_state,
            operational_state=self._operational_state,
            component_states={
                component_id: state.value
                for component_id, state in self._registry.states().items()
            },
            component_health={
                info.component_id: info.health_score
                for info in self._registry.list_components()
            },
            active_recoveries=list(self._active_recoveries),
            consistency_status=self._consistency_status,
            risk_integrity=self._risk_integrity,
            trading_gate=gate_result,
        )

    def save_snapshot(self) -> ControlPlaneSnapshot:
        snapshot = self.build_snapshot()
        self.repository.save_snapshot(snapshot)
        return snapshot

    def get_snapshot(self) -> ControlPlaneSnapshot:
        """Return the current projection, building it on demand when absent."""
        snapshot = self.repository.get_snapshot()
        if snapshot is not None:
            return snapshot
        return self.save_snapshot()

    def rebuild_snapshot(self) -> ControlPlaneSnapshot:
        """
        Rebuild the operational view purely from the event log.

        The snapshot is a projection, not a source of truth — the event log
        is replayed to reconstruct component states, system state and trading
        state, then the operational state / gate are recomputed.
        """
        replay = self.repository.replay_events()
        self._registry = self.repository.rebuild_registry()
        self._system_state = replay["system_state"]
        self._trading_state = replay["trading_state"]
        self._operational_state = self._recompute_operational_state()
        self._gate_result = self._gate.evaluate(
            self._registry.states(), self._risk_integrity
        )
        self._save_snapshot()
        return self.get_snapshot()

    def _recompute_operational_state(self) -> OperationalState:
        if self._emergency or self._risk_integrity is RiskIntegrity.UNTRUSTED:
            return OperationalState.EMERGENCY
        if self._system_state is SystemState.MAINTENANCE:
            return OperationalState.MAINTENANCE
        if (
            self._manual_halt
            or self._system_state is SystemState.HALTED
            or self._trading_state is TradingState.TRADING_HALTED
        ):
            return OperationalState.HALT
        if self._recovery_active or any(
            info.state is ComponentState.RECOVERING
            for info in self._registry.list_components()
        ):
            return OperationalState.RECOVERY
        if (
            self._system_state is SystemState.DEGRADED
            or self._trading_state is TradingState.TRADING_DEGRADED
        ):
            return OperationalState.DEGRADED
        return OperationalState.NORMAL

    # ======================================================================
    # Events
    # ======================================================================

    def collect_events(self) -> List[Any]:
        """Drain and return all events emitted since the last collect."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    # ======================================================================
    # Internals
    # ======================================================================

    def _emit(self, event: Any) -> None:
        event.event_id = self.repository.append_event(event)
        self._pending_events.append(event)

    def _apply_system_transition(
        self,
        new_state: SystemState,
        reason: StateReasonCode,
        source: str = "control-plane",
    ) -> None:
        if new_state is self._system_state:
            return
        SystemStateMachine.assert_transition(self._system_state, new_state)
        self._emit(
            SystemStateChanged.from_change(
                previous_state=self._system_state,
                new_state=new_state,
                reason=reason,
                source=source,
            )
        )
        self._system_state = new_state

    def _apply_trading_transition(
        self,
        new_state: TradingState,
        reason: StateReasonCode,
        gate_decision: str = "",
    ) -> None:
        if new_state is self._trading_state:
            return
        TradingStateMachine.assert_transition(self._trading_state, new_state)
        self._emit(
            TradingStateChanged.from_change(
                previous_state=self._trading_state,
                new_state=new_state,
                reason=reason,
                gate_decision=gate_decision,
            )
        )
        self._trading_state = new_state

    def _evaluate_and_persist(self) -> EvaluateTradingStateResult:
        return self.evaluate()

    def _save_snapshot(self) -> None:
        self.repository.save_snapshot(self.build_snapshot())
