"""
SystemState — the top-level state of the whole ICYQuant instance.

The System State Machine enforces that states can only move along allowed
transitions:

    INITIALIZING
          |
          v
       STARTING
          |
          v
        READY -----------------------------------------> MAINTENANCE
          |                                                |
          |                                                v
          v                                              READY
       DEGRADED
          |
          v
      RECOVERING
          |
          v
        READY

        READY / DEGRADED / RECOVERING / STARTING
            |
            v
         HALTED  ------>  STARTING (restart)

        ANY  ------>  FAILED  ------>  STARTING / MAINTENANCE
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class SystemState(str, Enum):
    """Top-level state of the ICYQuant system."""

    INITIALIZING = "INITIALIZING"
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    HALTED = "HALTED"
    FAILED = "FAILED"
    MAINTENANCE = "MAINTENANCE"


class StateReasonCode(str, Enum):
    """Every state change must carry a reason — no reason, no change."""

    SYSTEM_STARTING = "SYSTEM_STARTING"
    STARTUP_COMPLETE = "STARTUP_COMPLETE"
    SYSTEM_HEALTHY = "SYSTEM_HEALTHY"
    EVENT_BUS_UNAVAILABLE = "EVENT_BUS_UNAVAILABLE"
    RISK_ENGINE_UNHEALTHY = "RISK_ENGINE_UNHEALTHY"
    EXECUTION_ENGINE_UNHEALTHY = "EXECUTION_ENGINE_UNHEALTHY"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    POSITION_RECOVERY = "POSITION_RECOVERY"
    POSITION_UNTRUSTED = "POSITION_UNTRUSTED"
    LEDGER_MISMATCH = "LEDGER_MISMATCH"
    RECOVERY_RUNNING = "RECOVERY_RUNNING"
    RISK_INTEGRITY_DEGRADED = "RISK_INTEGRITY_DEGRADED"
    MANUAL_HALT = "MANUAL_HALT"
    EMERGENCY_HALT = "EMERGENCY_HALT"
    MAINTENANCE = "MAINTENANCE"
    COMPONENT_FAILED = "COMPONENT_FAILED"
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"
    HEARTBEAT_RESTORED = "HEARTBEAT_RESTORED"
    RESTART_REQUESTED = "RESTART_REQUESTED"
    RESUME_REQUESTED = "RESUME_REQUESTED"


class StateTransitionError(Exception):
    """Raised when a state transition is rejected by the state machine."""

    def __init__(self, from_state: SystemState, to_state: SystemState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid system state transition: {from_state.value} -> {to_state.value}")


class SystemStateMachine:
    """Explicit System State Machine — states cannot be set arbitrarily."""

    ALLOWED_TRANSITIONS: Dict[SystemState, Set[SystemState]] = {
        SystemState.INITIALIZING: {SystemState.STARTING, SystemState.FAILED},
        SystemState.STARTING: {SystemState.READY, SystemState.HALTED, SystemState.FAILED},
        SystemState.READY: {
            SystemState.DEGRADED,
            SystemState.HALTED,
            SystemState.MAINTENANCE,
            SystemState.FAILED,
        },
        SystemState.DEGRADED: {
            SystemState.RECOVERING,
            SystemState.READY,
            SystemState.HALTED,
            SystemState.FAILED,
        },
        SystemState.RECOVERING: {
            SystemState.READY,
            SystemState.DEGRADED,
            SystemState.HALTED,
            SystemState.FAILED,
        },
        SystemState.HALTED: {SystemState.STARTING, SystemState.FAILED},
        SystemState.MAINTENANCE: {
            SystemState.READY,
            SystemState.STARTING,
            SystemState.FAILED,
        },
        SystemState.FAILED: {SystemState.STARTING, SystemState.MAINTENANCE},
    }

    @classmethod
    def can_transition(cls, from_state: SystemState, to_state: SystemState) -> bool:
        return to_state in cls.ALLOWED_TRANSITIONS.get(from_state, set())

    @classmethod
    def assert_transition(cls, from_state: SystemState, to_state: SystemState) -> None:
        if not cls.can_transition(from_state, to_state):
            raise StateTransitionError(from_state, to_state)

    @classmethod
    def validate(cls, state: object) -> SystemState:
        """Coerce/validate a raw value into a SystemState."""
        if isinstance(state, SystemState):
            return state
        return SystemState(str(state))
