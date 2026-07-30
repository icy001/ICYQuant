"""
ICYQuant Platform - Lifecycle Manager

Manages the startup, shutdown, and transition phases of platform modules.
Follows a defined lifecycle: REGISTERED → INITIALIZING → RUNNING → PAUSED → STOPPED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LifecyclePhase(str, Enum):
    BOOT = "boot"
    INITIALIZE = "initialize"
    START = "start"
    RUN = "run"
    PAUSE = "pause"
    RESUME = "resume"
    SHUTDOWN = "shutdown"
    CLEANUP = "cleanup"


class LifecycleState(str, Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


@dataclass
class LifecycleTransition:
    from_state: LifecycleState
    to_state: LifecycleState
    allowed: bool = True
    handler: Optional[Callable] = None


@dataclass
class LifecycleRecord:
    module_name: str
    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict:
        return {
            "module": self.module_name,
            "from": self.from_state.value,
            "to": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error": self.error_message,
        }


class LifecycleManager:
    """
    Manages lifecycle transitions for all platform modules.

    Validates state transitions and triggers registered handlers.
    Maintains a complete audit trail of all state changes.
    """

    def __init__(self):
        self._state: Dict[str, LifecycleState] = {}
        self._handlers: Dict[str, Dict[LifecyclePhase, List[Callable]]] = {}
        self._transition_rules: List[LifecycleTransition] = [
            LifecycleTransition(LifecycleState.PENDING, LifecycleState.INITIALIZING),
            LifecycleTransition(LifecycleState.INITIALIZING, LifecycleState.INITIALIZED),
            LifecycleTransition(LifecycleState.INITIALIZED, LifecycleState.STARTING),
            LifecycleTransition(LifecycleState.STARTING, LifecycleState.RUNNING),
            LifecycleTransition(LifecycleState.RUNNING, LifecycleState.PAUSING),
            LifecycleTransition(LifecycleState.PAUSING, LifecycleState.PAUSED),
            LifecycleTransition(LifecycleState.PAUSED, LifecycleState.RESUMING),
            LifecycleTransition(LifecycleState.RESUMING, LifecycleState.RUNNING),
            LifecycleTransition(LifecycleState.RUNNING, LifecycleState.STOPPING),
            LifecycleTransition(LifecycleState.STOPPING, LifecycleState.STOPPED),
            LifecycleTransition(LifecycleState.PAUSED, LifecycleState.STOPPING),
            LifecycleTransition(LifecycleState.STOPPING, LifecycleState.STOPPED),
            LifecycleTransition(LifecycleState.RUNNING, LifecycleState.DEGRADED),
            LifecycleTransition(LifecycleState.DEGRADED, LifecycleState.RUNNING),
            LifecycleTransition(LifecycleState.DEGRADED, LifecycleState.STOPPING),
            LifecycleTransition(LifecycleState.PENDING, LifecycleState.ERROR),
            LifecycleTransition(LifecycleState.INITIALIZING, LifecycleState.ERROR),
            LifecycleTransition(LifecycleState.RUNNING, LifecycleState.ERROR),
            LifecycleTransition(LifecycleState.ERROR, LifecycleState.INITIALIZING),
        ]
        self._history: List[LifecycleRecord] = []
        self._max_history = 1000

    def register_module(self, name: str, initial_state: LifecycleState = LifecycleState.PENDING):
        self._state[name] = initial_state
        if name not in self._handlers:
            self._handlers[name] = {}
        logger.info(f"Lifecycle registered: {name} -> {initial_state.value}")

    def get_state(self, name: str) -> LifecycleState:
        return self._state.get(name, LifecycleState.PENDING)

    def can_transition(self, name: str, target: LifecycleState) -> bool:
        current = self._state.get(name, LifecycleState.PENDING)
        for rule in self._transition_rules:
            if rule.from_state == current and rule.to_state == target:
                return rule.allowed
        return False

    def transition(self, name: str, target: LifecycleState) -> bool:
        current = self._state.get(name, LifecycleState.PENDING)
        if not self.can_transition(name, target):
            logger.warning(
                f"Invalid transition for '{name}': {current.value} -> {target.value}"
            )
            self._record_transition(name, current, target, False, "Invalid transition")
            return False

        handlers = self._handlers.get(name, {})
        phase = self._state_to_phase(current, target)
        for handler in handlers.get(phase, []):
            try:
                handler(name, current, target)
            except Exception as e:
                logger.error(f"Handler error during {phase.value} for '{name}': {e}")
                self._record_transition(name, current, target, False, str(e))
                self._state[name] = LifecycleState.ERROR
                return False

        self._state[name] = target
        self._record_transition(name, current, target, True)
        logger.info(f"Lifecycle: {name} {current.value} -> {target.value}")
        return True

    def on_phase(self, name: str, phase: LifecyclePhase, handler: Callable):
        if name not in self._handlers:
            self._handlers[name] = {}
        if phase not in self._handlers[name]:
            self._handlers[name][phase] = []
        self._handlers[name][phase].append(handler)

    def initialize(self, name: str) -> bool:
        return self.transition(name, LifecycleState.INITIALIZING)

    def start(self, name: str) -> bool:
        if self.get_state(name) == LifecycleState.PENDING:
            self.transition(name, LifecycleState.INITIALIZING)
            self.transition(name, LifecycleState.INITIALIZED)
        if self.get_state(name) in (LifecycleState.INITIALIZED, LifecycleState.PAUSED):
            target = LifecycleState.STARTING if self.get_state(name) != LifecycleState.PAUSED else LifecycleState.RESUMING
            self.transition(name, target)
        return self.transition(name, LifecycleState.RUNNING)

    def pause(self, name: str) -> bool:
        if self.get_state(name) == LifecycleState.RUNNING:
            self.transition(name, LifecycleState.PAUSING)
        return self.transition(name, LifecycleState.PAUSED)

    def resume(self, name: str) -> bool:
        if self.get_state(name) == LifecycleState.PAUSED:
            self.transition(name, LifecycleState.RESUMING)
        return self.transition(name, LifecycleState.RUNNING)

    def stop(self, name: str) -> bool:
        current = self.get_state(name)
        if current in (LifecycleState.RUNNING, LifecycleState.PAUSED, LifecycleState.DEGRADED):
            self.transition(name, LifecycleState.STOPPING)
        return self.transition(name, LifecycleState.STOPPED)

    def mark_error(self, name: str) -> bool:
        current = self.get_state(name)
        return self.transition(name, LifecycleState.ERROR)

    def get_history(self, module_name: Optional[str] = None, limit: int = 100) -> List[LifecycleRecord]:
        records = self._history
        if module_name:
            records = [r for r in records if r.module_name == module_name]
        return records[-limit:]

    def _record_transition(self, name: str, from_state: LifecycleState, to_state: LifecycleState, success: bool, error: str = ""):
        record = LifecycleRecord(
            module_name=name,
            from_state=from_state,
            to_state=to_state,
            success=success,
            error_message=error,
        )
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def _state_to_phase(self, old_state: LifecycleState, new_state: LifecycleState) -> LifecyclePhase:
        phases = {
            (LifecycleState.PENDING, LifecycleState.INITIALIZING): LifecyclePhase.INITIALIZE,
            (LifecycleState.INITIALIZED, LifecycleState.STARTING): LifecyclePhase.START,
            (LifecycleState.STARTING, LifecycleState.RUNNING): LifecyclePhase.RUN,
            (LifecycleState.RUNNING, LifecycleState.PAUSING): LifecyclePhase.PAUSE,
            (LifecycleState.PAUSED, LifecycleState.RESUMING): LifecyclePhase.RESUME,
            (LifecycleState.RUNNING, LifecycleState.STOPPING): LifecyclePhase.SHUTDOWN,
            (LifecycleState.STOPPING, LifecycleState.STOPPED): LifecyclePhase.CLEANUP,
        }
        return phases.get((old_state, new_state), LifecyclePhase.RUN)

    def get_status(self) -> Dict:
        return {
            "states": {name: state.value for name, state in self._state.items()},
            "totalTransitions": len(self._history),
            "activeModules": sum(
                1 for s in self._state.values()
                if s in (LifecycleState.RUNNING, LifecycleState.STARTING)
            ),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
