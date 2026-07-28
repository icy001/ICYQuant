"""Runtime Mode Manager – manages trading runtime modes (Paper, Simulation, Shadow, Live, Safe)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class RuntimeMode(Enum):
    PAPER = "paper"
    SIMULATION = "simulation"
    SHADOW = "shadow"
    LIVE = "live"
    SAFE_MODE = "safe_mode"


@dataclass
class ModeTransition:
    from_mode: RuntimeMode
    to_mode: RuntimeMode
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeModeManager:
    """Manages switching between trading runtime modes.

    Modes:
      - PAPER: paper trading, no real orders.
      - SIMULATION: full simulation with market data.
      - SHADOW: shadow live — tracks what would have traded.
      - LIVE: real trading with real money.
      - SAFE_MODE: emergency safe mode — all trading suspended.
    """

    # Allowed transitions
    ALLOWED_TRANSITIONS = {
        RuntimeMode.PAPER: {RuntimeMode.SIMULATION, RuntimeMode.SHADOW},
        RuntimeMode.SIMULATION: {RuntimeMode.PAPER, RuntimeMode.SHADOW, RuntimeMode.LIVE},
        RuntimeMode.SHADOW: {RuntimeMode.PAPER, RuntimeMode.SIMULATION, RuntimeMode.LIVE},
        RuntimeMode.LIVE: {RuntimeMode.SHADOW, RuntimeMode.SAFE_MODE},
        RuntimeMode.SAFE_MODE: {RuntimeMode.PAPER, RuntimeMode.SIMULATION},
    }

    def __init__(self, initial_mode: RuntimeMode = RuntimeMode.PAPER) -> None:
        self._current_mode = initial_mode
        self._transition_history: List[ModeTransition] = []

    def switch(self, mode: str) -> str:
        """Switch to a given mode (by string name).

        Args:
            mode: target mode name (e.g. "paper", "live").

        Returns:
            The current mode string after switch.
        """
        target = RuntimeMode(mode.lower())
        return self._switch_to(target).value

    def _switch_to(self, target: RuntimeMode) -> RuntimeMode:
        """Internal switch with validation."""
        if target == self._current_mode:
            return target

        allowed = self.ALLOWED_TRANSITIONS.get(self._current_mode, set())
        if target not in allowed:
            # Allow forced transition to safe mode from any mode
            if target != RuntimeMode.SAFE_MODE:
                # Silently stay in current mode for invalid transitions
                return self._current_mode

        transition = ModeTransition(
            from_mode=self._current_mode,
            to_mode=target,
        )
        self._transition_history.append(transition)
        self._current_mode = target
        return target

    def safe_mode(self, reason: str = "Emergency") -> RuntimeMode:
        """Force switch to safe mode."""
        transition = ModeTransition(
            from_mode=self._current_mode,
            to_mode=RuntimeMode.SAFE_MODE,
            reason=reason,
        )
        self._transition_history.append(transition)
        self._current_mode = RuntimeMode.SAFE_MODE
        return self._current_mode

    @property
    def current_mode(self) -> RuntimeMode:
        return self._current_mode

    @property
    def current_mode_value(self) -> str:
        return self._current_mode.value

    def can_switch_to(self, target: str) -> bool:
        """Check if transition to target mode is allowed."""
        try:
            t = RuntimeMode(target.lower())
            return t in self.ALLOWED_TRANSITIONS.get(self._current_mode, set())
        except ValueError:
            return False

    def get_transition_history(self, n: int = 20) -> List[ModeTransition]:
        return self._transition_history[-n:]

    def is_live(self) -> bool:
        return self._current_mode == RuntimeMode.LIVE

    def is_safe(self) -> bool:
        return self._current_mode == RuntimeMode.SAFE_MODE

    @property
    def transition_count(self) -> int:
        return len(self._transition_history)
