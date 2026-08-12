"""
ICYQuant Production Control Plane (Commit 24 Part 1.1).

The Control Plane answers the production questions:

    * What state is the whole system in right now?
    * Which components are healthy?
    * Can we trade right now?
    * When must trading stop?
    * When can trading resume?

State model (4 layers):

    System State       INITIALIZING → STARTING → READY / DEGRADED / RECOVERING / HALTED / FAILED / MAINTENANCE
    Component State    STARTING / HEALTHY / DEGRADED / UNHEALTHY / RECOVERING / STOPPED / UNKNOWN
    Trading State      TRADING_DISABLED / TRADING_READY / TRADING_DEGRADED / TRADING_HALTED
    Operational State  NORMAL / DEGRADED / RECOVERY / HALT / MAINTENANCE / EMERGENCY

Everything is event-driven: evaluation produces a StateDecision, the decision
is emitted as STATE_CHANGED events, and the ControlPlaneSnapshot is a
projection that can always be rebuilt by replaying the event log.
"""

from .commands import (
    EvaluateTradingState,
    EvaluateTradingStateResult,
    UpdateComponentState,
    UpdateComponentStateResult,
)
from .domain import (
    ComponentCriticality,
    ComponentInfo,
    ComponentRegistry,
    ComponentState,
    ComponentType,
    ControlPlaneSnapshot,
    ControlPolicy,
    GateDecision,
    OperationalState,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
    RiskIntegrity,
    Severity,
    StateDecision,
    StateReasonCode,
    StateTransitionError,
    SystemState,
    SystemStateMachine,
    TradingGate,
    TradingGateResult,
    TradingPolicy,
    TradingState,
    TradingStateMachine,
    TradingStateTransitionError,
)
from .events import (
    ComponentStateChanged,
    SystemStateChanged,
    TradingStateChanged,
)
from .repositories import ControlPlaneRepository
from .services import ControlPlaneService

__all__ = [
    "ComponentCriticality",
    "ComponentInfo",
    "ComponentRegistry",
    "ComponentState",
    "ComponentStateChanged",
    "ComponentType",
    "ControlPlaneRepository",
    "ControlPlaneService",
    "ControlPlaneSnapshot",
    "ControlPolicy",
    "EvaluateTradingState",
    "EvaluateTradingStateResult",
    "GateDecision",
    "OperationalState",
    "PolicyContext",
    "PolicyDecision",
    "PolicyResult",
    "RiskIntegrity",
    "Severity",
    "StateDecision",
    "StateReasonCode",
    "StateTransitionError",
    "SystemState",
    "SystemStateChanged",
    "SystemStateMachine",
    "TradingGate",
    "TradingGateResult",
    "TradingPolicy",
    "TradingState",
    "TradingStateChanged",
    "TradingStateMachine",
    "TradingStateTransitionError",
    "UpdateComponentState",
    "UpdateComponentStateResult",
]
