"""
EvaluateTradingState — the periodic evaluation that derives:

    System State  +  Trading State  +  Operational State

from the current component states, consistency state, recovery state and Risk
Integrity.  Evaluation produces a StateDecision; it never writes state
directly — the service turns the decision into STATE_CHANGED events.

    evaluate()
        │
        ▼
    StateDecision
        │
        ▼
    SYSTEM_STATE_CHANGED / TRADING_STATE_CHANGED   (emitted by the service)
        │
        ▼
    Projection (snapshot)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..domain.component_registry import ComponentRegistry, ComponentType
from ..domain.component_state import ComponentState
from ..domain.control_policy import (
    ControlPolicy,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
    TradingPolicy,
)
from ..domain.operational_state import OperationalState
from ..domain.state_decision import StateDecision
from ..domain.system_state import StateReasonCode, SystemState, SystemStateMachine
from ..domain.trading_gate import (
    GateDecision,
    RiskIntegrity,
    Severity,
    TradingGate,
    TradingGateResult,
)
from ..domain.trading_state import TradingState, TradingStateMachine

#: OPERATIONAL components whose degradation constrains (but does not halt) trading.
_DEGRADE_TRADING_IDS: tuple = (
    ComponentType.POSITION_SERVICE.value,
    ComponentType.LEDGER_SERVICE.value,
    ComponentType.ORDER_ENGINE.value,
    ComponentType.STRATEGY_ENGINE.value,
    ComponentType.RECONCILIATION_ENGINE.value,
    ComponentType.RECOVERY_ENGINE.value,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EvaluateTradingStateResult:
    """Output of an evaluation — states to apply + decision behind them."""

    system_state: SystemState
    trading_state: TradingState
    operational_state: OperationalState
    gate_result: TradingGateResult
    policy_result: PolicyResult
    decision: StateDecision
    system_changed: bool
    trading_changed: bool


@dataclass
class EvaluateTradingState:
    """Command: recompute system / trading / operational state from inputs."""

    current_system_state: SystemState
    current_trading_state: TradingState
    current_operational_state: OperationalState
    policy: ControlPolicy = field(default_factory=TradingPolicy)
    gate: TradingGate = field(default_factory=TradingGate)
    consistency_status: Optional[str] = None
    recovery_active: bool = False
    risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    manual_halt: bool = False
    emergency: bool = False
    at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(self, registry: ComponentRegistry) -> EvaluateTradingStateResult:
        at = self.at or _utcnow()
        states: Dict[str, ComponentState] = registry.states()
        any_recovering = any(
            state is ComponentState.RECOVERING for state in states.values()
        )

        policy_result = self.policy.evaluate(
            PolicyContext(
                component_states=states,
                risk_integrity=self.risk_integrity,
                consistency_status=self.consistency_status,
                recovery_active=self.recovery_active,
            )
        )
        gate_result = self.gate.evaluate(states, self.risk_integrity, at=at)

        trading_state = self._derive_trading_state(states, gate_result)
        system_state = self._derive_system_state(states, gate_result)
        operational_state = self._derive_operational_state(
            system_state, trading_state, any_recovering
        )

        # State machines — reject truly invalid transitions, fall back otherwise.
        system_state = self._validated_system_state(system_state)
        trading_state = self._validated_trading_state(trading_state)

        decision = self._build_decision(gate_result, policy_result)
        return EvaluateTradingStateResult(
            system_state=system_state,
            trading_state=trading_state,
            operational_state=operational_state,
            gate_result=gate_result,
            policy_result=policy_result,
            decision=decision,
            system_changed=system_state is not self.current_system_state,
            trading_changed=trading_state is not self.current_trading_state,
        )

    # ------------------------------------------------------------------
    # derivations
    # ------------------------------------------------------------------

    def _derive_trading_state(
        self,
        states: Dict[str, ComponentState],
        gate_result: TradingGateResult,
    ) -> TradingState:
        # Startup phase — trading stays disabled until startup completes.
        if self.current_system_state in (SystemState.INITIALIZING, SystemState.STARTING):
            return TradingState.TRADING_DISABLED

        # Maintenance / failure — trading is suspended.
        if self.current_system_state in (
            SystemState.MAINTENANCE,
            SystemState.FAILED,
        ):
            return TradingState.TRADING_HALTED

        # Any hard block (gate, manual halt, emergency) halts trading.
        if (
            self.manual_halt
            or self.emergency
            or gate_result.decision is GateDecision.DENY
        ):
            return TradingState.TRADING_HALTED

        # Position / Ledger / core-adjacent components degraded → constrained.
        if self.risk_integrity is RiskIntegrity.DEGRADED or any(
            states.get(cid) is not None and states[cid] is not ComponentState.HEALTHY
            for cid in _DEGRADE_TRADING_IDS
        ):
            return TradingState.TRADING_DEGRADED

        return TradingState.TRADING_READY

    def _derive_system_state(
        self,
        states: Dict[str, ComponentState],
        gate_result: TradingGateResult,
    ) -> SystemState:
        # Startup phase is managed explicitly (start / complete_startup).
        if self.current_system_state in (SystemState.INITIALIZING, SystemState.STARTING):
            return self.current_system_state

        # Maintenance is a controlled window — never auto-exits during evaluation.
        if self.current_system_state is SystemState.MAINTENANCE:
            return SystemState.MAINTENANCE

        # Emergency or a denied gate → system cannot run the trading core.
        if self.emergency or gate_result.decision is GateDecision.DENY:
            return SystemState.HALTED

        # Recovery engine is actively repairing something.
        if self.recovery_active:
            return SystemState.RECOVERING

        # Risk inputs are impaired but still usable → degraded.
        if self.risk_integrity is RiskIntegrity.DEGRADED:
            return SystemState.DEGRADED

        # Any component not fully healthy → degraded.
        if any(state is not ComponentState.HEALTHY for state in states.values()):
            return SystemState.DEGRADED

        return SystemState.READY

    def _build_decision(
        self,
        gate_result: TradingGateResult,
        policy_result: PolicyResult,
    ) -> StateDecision:
        """Derive an auditable decision (with the *real* cause) for this evaluation."""
        if self.emergency:
            return StateDecision.from_values(
                decision="TRADING_DENY",
                reason=StateReasonCode.EMERGENCY_HALT,
                severity=Severity.CRITICAL,
                source="emergency-halt",
            )
        if self.manual_halt:
            return StateDecision.from_values(
                decision="TRADING_DENY",
                reason=StateReasonCode.MANUAL_HALT,
                severity=Severity.CRITICAL,
                source="manual-halt",
            )
        if gate_result.decision is GateDecision.DENY:
            return StateDecision.from_gate(gate_result)
        if policy_result.decision is PolicyDecision.REVIEW:
            return StateDecision.from_values(
                decision="TRADING_REVIEW",
                reason=policy_result.reason,
                severity=policy_result.severity,
                source=policy_result.source,
            )
        return StateDecision.from_gate(gate_result)

    def _derive_operational_state(
        self,
        system_state: SystemState,
        trading_state: TradingState,
        any_recovering: bool,
    ) -> OperationalState:
        if self.emergency or self.risk_integrity is RiskIntegrity.UNTRUSTED:
            return OperationalState.EMERGENCY

        if system_state is SystemState.MAINTENANCE:
            return OperationalState.MAINTENANCE

        if (
            self.manual_halt
            or self.current_system_state is SystemState.HALTED
            or trading_state is TradingState.TRADING_HALTED
        ):
            return OperationalState.HALT

        if self.recovery_active or any_recovering:
            return OperationalState.RECOVERY

        if system_state is SystemState.DEGRADED or trading_state is TradingState.TRADING_DEGRADED:
            return OperationalState.DEGRADED

        return OperationalState.NORMAL

    # ------------------------------------------------------------------
    # state machine validation with graceful fallback
    # ------------------------------------------------------------------

    def _validated_system_state(self, desired: SystemState) -> SystemState:
        current = self.current_system_state
        if desired is current or SystemStateMachine.can_transition(current, desired):
            return desired
        # Follow the closest valid path instead of crashing evaluation.
        if desired is SystemState.RECOVERING and current is SystemState.READY:
            return SystemState.DEGRADED  # READY → DEGRADED → RECOVERING
        if desired is SystemState.READY and current is SystemState.HALTED:
            return SystemState.STARTING  # HALTED → STARTING → READY (restart cycle)
        # FAILED requires an explicit restart() — never auto-restart.
        return current

    def _validated_trading_state(self, desired: TradingState) -> TradingState:
        current = self.current_trading_state
        if desired is current or TradingStateMachine.can_transition(current, desired):
            return desired
        return current
