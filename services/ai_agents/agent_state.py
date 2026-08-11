"""
ICYQuant Agent State — state machine for individual agent lifecycle.

Tracks agent internal state transitions and provides state-dependent
behavior control for all agent types.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    RECEIVING = "receiving"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    DEBATING = "debating"
    VOTING = "voting"
    COMPLETING = "completing"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentStateMachine:
    """State machine for agent lifecycle management.

    Valid transitions:
        INITIALIZING → IDLE
        IDLE → RECEIVING
        RECEIVING → THINKING
        THINKING → EXECUTING
        EXECUTING → WAITING | DEBATING | VOTING
        WAITING → THINKING | ERROR
        DEBATING → VOTING | WAITING
        VOTING → COMPLETING
        COMPLETING → IDLE
        Any → ERROR
        Any → SHUTDOWN
    """

    VALID_TRANSITIONS = {
        AgentState.INITIALIZING: {AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.IDLE: {AgentState.RECEIVING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.RECEIVING: {AgentState.THINKING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.THINKING: {AgentState.EXECUTING, AgentState.WAITING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.EXECUTING: {AgentState.WAITING, AgentState.DEBATING, AgentState.VOTING, AgentState.COMPLETING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.WAITING: {AgentState.THINKING, AgentState.RECEIVING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.DEBATING: {AgentState.VOTING, AgentState.WAITING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.VOTING: {AgentState.COMPLETING, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.COMPLETING: {AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN},
        AgentState.ERROR: {AgentState.IDLE, AgentState.SHUTDOWN},
        AgentState.SHUTDOWN: set(),
    }

    def __init__(self) -> None:
        self._state = AgentState.INITIALIZING
        self._state_history: list[tuple[AgentState, datetime]] = [(AgentState.INITIALIZING, datetime.now(timezone.utc))]

    def transition(self, new_state: AgentState) -> bool:
        """Attempt a state transition. Returns True if valid."""
        if new_state not in self.VALID_TRANSITIONS.get(self._state, set()):
            logger.warning("Invalid transition: %s → %s", self._state.value, new_state.value)
            return False

        self._state = new_state
        self._state_history.append((new_state, datetime.now(timezone.utc)))
        logger.debug("State: %s", new_state.value)
        return True

    def force_transition(self, new_state: AgentState) -> None:
        """Force a state transition, bypassing validation."""
        self._state = new_state
        self._state_history.append((new_state, datetime.now(timezone.utc)))

    @property
    def current_state(self) -> AgentState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state not in (AgentState.ERROR, AgentState.SHUTDOWN, AgentState.INITIALIZING)

    @property
    def is_busy(self) -> bool:
        return self._state in (AgentState.THINKING, AgentState.EXECUTING, AgentState.DEBATING, AgentState.VOTING)

    @property
    def history(self) -> list[dict[str, Any]]:
        return [
            {"state": s.value, "timestamp": ts.isoformat()}
            for s, ts in self._state_history
        ]
