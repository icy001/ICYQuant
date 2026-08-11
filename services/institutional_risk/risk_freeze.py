"""RiskFreeze — risk freeze logic for defensive/emergency modes.

Freezes new risk-taking while still allowing:
- Position reduction
- Hedging
- Risk closure
- Emergency exit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class FreezeLevel(Enum):
    """Risk freeze levels."""

    NONE = auto()           # No freeze
    SELECTIVE = auto()      # Freeze only high-risk additions
    COMPREHENSIVE = auto()  # Freeze all new risk
    ABSOLUTE = auto()       # Emergency: only reduce


@dataclass
class FreezeState:
    """Current freeze state."""

    level: FreezeLevel = FreezeLevel.NONE
    reason: str = ""
    frozen_since: float = 0.0
    allowed_actions: Set[str] = field(default_factory=set)
    blocked_entities: Set[str] = field(default_factory=set)


class RiskFreezeController:
    """Controls risk freeze during defensive and emergency modes.

    Usage::

        controller = RiskFreezeController()
        controller.freeze(FreezeLevel.COMPREHENSIVE, "Survival score < 40")
        if controller.is_blocked("strat_A", "INCREASE"):
            print("Action blocked by risk freeze")
    """

    def __init__(self):
        import time
        self._state = FreezeState()
        self._state.allowed_actions = {
            "REDUCE",
            "HEDGE",
            "CLOSE",
            "EXIT",
            "REDUCE_LEVERAGE",
        }
        self._blocked_actions = {
            "INCREASE",
            "ADD",
            "LEVERAGE_UP",
            "NEW_POSITION",
        }

    @property
    def level(self) -> FreezeLevel:
        return self._state.level

    @property
    def is_frozen(self) -> bool:
        return self._state.level != FreezeLevel.NONE

    def freeze(
        self,
        level: FreezeLevel,
        reason: str = "",
        blocked_entities: Optional[Set[str]] = None,
    ) -> None:
        """Activate a risk freeze.

        Args:
            level: freeze level
            reason: why the freeze is activated
            blocked_entities: specific entities to block
        """
        import time
        self._state.level = level
        self._state.reason = reason
        self._state.frozen_since = time.time()
        if blocked_entities:
            self._state.blocked_entities = blocked_entities

    def unfreeze(self) -> None:
        """Remove all freezes."""
        self._state = FreezeState()
        self._state.allowed_actions = {
            "REDUCE", "HEDGE", "CLOSE", "EXIT", "REDUCE_LEVERAGE",
        }

    def is_allowed(
        self,
        action_type: str,
        entity_id: str = "",
    ) -> bool:
        """Check if an action is allowed under current freeze.

        Args:
            action_type: action type string
            entity_id: target entity (for selective freeze)
        """
        if self._state.level == FreezeLevel.NONE:
            return True

        # UNDER ALL FREEZE LEVELS, reduction/hedge/exit is ALWAYS allowed
        if action_type in self._state.allowed_actions:
            return True

        # selective: block based on entity
        if self._state.level == FreezeLevel.SELECTIVE:
            if entity_id and entity_id in self._state.blocked_entities:
                return False
            # check if this is a risk-increasing action
            if action_type in self._blocked_actions:
                return False
            return True

        # comprehensive/absolute: block all risk-increasing actions
        if action_type in self._blocked_actions:
            return False

        return True

    def is_blocked(
        self,
        entity_id: str,
        action_type: str,
    ) -> bool:
        """Check if an action is blocked. Inverse of is_allowed."""
        return not self.is_allowed(action_type, entity_id)

    def get_state(self) -> Dict[str, Any]:
        """Get current freeze state."""
        return {
            "level": self._state.level.name,
            "reason": self._state.reason,
            "frozen_since": self._state.frozen_since,
            "blocked_entities": list(self._state.blocked_entities),
        }
