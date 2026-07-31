"""Platform lifecycle management."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

class LifecycleState(str, Enum):
    CREATED = "created"
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

class LifecyclePhase(str, Enum):
    INITIALIZE = "initialize"
    START = "start"
    RUN = "run"
    PAUSE = "pause"
    RESUME = "resume"
    SHUTDOWN = "shutdown"
    CLEANUP = "cleanup"

VALID_TRANSITIONS: Dict[LifecycleState, List[LifecycleState]] = {
    LifecycleState.CREATED: [LifecycleState.INITIALIZING],
    LifecycleState.INITIALIZING: [LifecycleState.INITIALIZED, LifecycleState.ERROR],
    LifecycleState.INITIALIZED: [LifecycleState.STARTING],
    LifecycleState.STARTING: [LifecycleState.RUNNING, LifecycleState.ERROR],
    LifecycleState.RUNNING: [LifecycleState.PAUSING, LifecycleState.STOPPING, LifecycleState.ERROR],
    LifecycleState.PAUSING: [LifecycleState.PAUSED, LifecycleState.ERROR],
    LifecycleState.PAUSED: [LifecycleState.RESUMING, LifecycleState.STOPPING],
    LifecycleState.RESUMING: [LifecycleState.RUNNING, LifecycleState.ERROR],
    LifecycleState.STOPPING: [LifecycleState.STOPPED, LifecycleState.ERROR],
    LifecycleState.ERROR: [LifecycleState.INITIALIZING, LifecycleState.STOPPED],
}

@dataclass
class LifecycleRecord:
    module_name: str
    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> dict:
        return {
            "module": self.module_name,
            "from": self.from_state.value,
            "to": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error": self.error_message,
        }

class LifecycleManager:
    """Manages lifecycle transitions for all modules."""

    def __init__(self):
        self._states: Dict[str, LifecycleState] = {}
        self._handlers: Dict[str, Dict[LifecyclePhase, List[Callable]]] = {}
        self._history: List[LifecycleRecord] = []
        self._max_history = 1000

    def register(self, name: str, initial_state: LifecycleState = LifecycleState.CREATED) -> None:
        self._states[name] = initial_state
        if name not in self._handlers:
            self._handlers[name] = {}

    def unregister(self, name: str) -> None:
        self._states.pop(name, None)
        self._handlers.pop(name, None)

    def get_state(self, name: str) -> LifecycleState:
        return self._states.get(name, LifecycleState.CREATED)

    def can_transition(self, name: str, target: LifecycleState) -> bool:
        current = self.get_state(name)
        allowed = VALID_TRANSITIONS.get(current, [])
        return target in allowed

    def transition(self, name: str, target: LifecycleState) -> bool:
        current = self.get_state(name)
        if not self.can_transition(name, target):
            self._record(name, current, target, False, f"Invalid transition: {current.value} -> {target.value}")
            return False

        phase = self._state_to_phase(current, target)
        for handler in self._handlers.get(name, {}).get(phase, []):
            try:
                handler(name, current, target)
            except Exception as e:
                self._record(name, current, target, False, str(e))
                self._states[name] = LifecycleState.ERROR
                return False

        self._states[name] = target
        self._record(name, current, target, True)
        return True

    def initialize(self, name: str) -> bool:
        return self.transition(name, LifecycleState.INITIALIZING)

    def start(self, name: str) -> bool:
        if self.get_state(name) == LifecycleState.CREATED:
            self.initialize(name)
            self.transition(name, LifecycleState.INITIALIZED)
        if self.get_state(name) in (LifecycleState.INITIALIZED, LifecycleState.PAUSED):
            self.transition(name, LifecycleState.STARTING)
        return self.transition(name, LifecycleState.RUNNING)

    def stop(self, name: str) -> bool:
        current = self.get_state(name)
        if current in (LifecycleState.RUNNING, LifecycleState.PAUSED):
            self.transition(name, LifecycleState.STOPPING)
        return self.transition(name, LifecycleState.STOPPED)

    def pause(self, name: str) -> bool:
        return self.transition(name, LifecycleState.PAUSING) and self.transition(name, LifecycleState.PAUSED)

    def resume(self, name: str) -> bool:
        return self.transition(name, LifecycleState.RESUMING) and self.transition(name, LifecycleState.RUNNING)

    def mark_error(self, name: str) -> bool:
        return self.transition(name, LifecycleState.ERROR)

    def on_phase(self, name: str, phase: LifecyclePhase, handler: Callable) -> None:
        if name not in self._handlers:
            self._handlers[name] = {}
        if phase not in self._handlers[name]:
            self._handlers[name][phase] = []
        self._handlers[name][phase].append(handler)

    def get_history(self, module_name: Optional[str] = None, limit: int = 100) -> List[LifecycleRecord]:
        records = self._history
        if module_name:
            records = [r for r in records if r.module_name == module_name]
        return records[-limit:]

    def get_status(self) -> dict:
        active = sum(1 for s in self._states.values() if s == LifecycleState.RUNNING)
        return {
            "states": {n: s.value for n, s in self._states.items()},
            "total_transitions": len(self._history),
            "active_modules": active,
            "total_modules": len(self._states),
        }

    def _record(self, name: str, from_state: LifecycleState, to_state: LifecycleState, success: bool, error: str = "") -> None:
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

    def _state_to_phase(self, old: LifecycleState, new: LifecycleState) -> LifecyclePhase:
        mapping = {
            (LifecycleState.CREATED, LifecycleState.INITIALIZING): LifecyclePhase.INITIALIZE,
            (LifecycleState.INITIALIZED, LifecycleState.STARTING): LifecyclePhase.START,
            (LifecycleState.STARTING, LifecycleState.RUNNING): LifecyclePhase.RUN,
            (LifecycleState.RUNNING, LifecycleState.PAUSING): LifecyclePhase.PAUSE,
            (LifecycleState.PAUSED, LifecycleState.RESUMING): LifecyclePhase.RESUME,
            (LifecycleState.RUNNING, LifecycleState.STOPPING): LifecyclePhase.SHUTDOWN,
            (LifecycleState.STOPPING, LifecycleState.STOPPED): LifecyclePhase.CLEANUP,
        }
        return mapping.get((old, new), LifecyclePhase.RUN)
