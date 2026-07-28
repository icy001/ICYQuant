"""Emergency Controller – kill switch, emergency liquidation, pause, and restart."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EmergencyAction(Enum):
    KILL_SWITCH = "STOP_ALL"
    EMERGENCY_LIQUIDATE = "LIQUIDATE_ALL"
    EMERGENCY_PAUSE = "PAUSE_ALL"
    EMERGENCY_RESTART = "RESTART"


@dataclass
class EmergencyEvent:
    action: EmergencyAction
    reason: str = ""
    triggered_by: str = "system"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmergencyController:
    """Handles emergency trading controls: kill switch, liquidation, pause, restart.

    The last line of defense for the entire trading system.
    """

    def __init__(self) -> None:
        self._is_active = False
        self._current_action: Optional[EmergencyAction] = None
        self._event_log: List[EmergencyEvent] = []

    def kill_switch(self, reason: str = "Manual kill switch", triggered_by: str = "operator") -> str:
        """Activate kill switch — stops ALL trading immediately.

        Returns:
            "STOP_ALL"
        """
        event = EmergencyEvent(
            action=EmergencyAction.KILL_SWITCH,
            reason=reason,
            triggered_by=triggered_by,
        )
        self._is_active = True
        self._current_action = EmergencyAction.KILL_SWITCH
        self._event_log.append(event)
        return EmergencyAction.KILL_SWITCH.value

    def emergency_liquidate(self, reason: str = "Emergency liquidation") -> str:
        """Initiate emergency liquidation of all positions."""
        event = EmergencyEvent(
            action=EmergencyAction.EMERGENCY_LIQUIDATE,
            reason=reason,
        )
        self._is_active = True
        self._current_action = EmergencyAction.EMERGENCY_LIQUIDATE
        self._event_log.append(event)
        return EmergencyAction.EMERGENCY_LIQUIDATE.value

    def emergency_pause(self, reason: str = "Emergency pause") -> str:
        """Pause all trading activity."""
        event = EmergencyEvent(
            action=EmergencyAction.EMERGENCY_PAUSE,
            reason=reason,
        )
        self._is_active = True
        self._current_action = EmergencyAction.EMERGENCY_PAUSE
        self._event_log.append(event)
        return EmergencyAction.EMERGENCY_PAUSE.value

    def restart(self, reason: str = "System restart") -> str:
        """Restart trading after an emergency stop."""
        event = EmergencyEvent(
            action=EmergencyAction.EMERGENCY_RESTART,
            reason=reason,
        )
        self._is_active = False
        self._current_action = None
        self._event_log.append(event)
        return EmergencyAction.EMERGENCY_RESTART.value

    def reset(self) -> None:
        """Reset emergency state."""
        self._is_active = False
        self._current_action = None

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def current_action(self) -> Optional[EmergencyAction]:
        return self._current_action

    def get_event_log(self, n: int = 20) -> List[EmergencyEvent]:
        return self._event_log[-n:]

    @property
    def event_count(self) -> int:
        return len(self._event_log)
