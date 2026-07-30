from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class EmergencyLevel(Enum):
    NORMAL = "NORMAL"
    ALERT = "ALERT"
    RESTRICT = "RESTRICT"
    HALT = "HALT"


@dataclass
class EmergencyState:
    level: str
    cancel_orders: bool
    disable_new_orders: bool
    freeze_agents: bool
    timestamp: int


class EmergencyController:
    def __init__(self):
        self.current_state = EmergencyState(
            level=EmergencyLevel.NORMAL.value,
            cancel_orders=False,
            disable_new_orders=False,
            freeze_agents=False,
            timestamp=0,
        )
        self.state_history: List[EmergencyState] = []

    def _record_state(self, state: EmergencyState):
        self.current_state = state
        self.state_history.append(state)

    def trigger_alert(self) -> EmergencyState:
        state = EmergencyState(
            level=EmergencyLevel.ALERT.value,
            cancel_orders=False,
            disable_new_orders=False,
            freeze_agents=False,
            timestamp=self._get_timestamp(),
        )
        self._record_state(state)
        return state

    def trigger_restrict(self) -> EmergencyState:
        state = EmergencyState(
            level=EmergencyLevel.RESTRICT.value,
            cancel_orders=False,
            disable_new_orders=True,
            freeze_agents=False,
            timestamp=self._get_timestamp(),
        )
        self._record_state(state)
        return state

    def trigger_halt(self) -> EmergencyState:
        state = EmergencyState(
            level=EmergencyLevel.HALT.value,
            cancel_orders=True,
            disable_new_orders=True,
            freeze_agents=True,
            timestamp=self._get_timestamp(),
        )
        self._record_state(state)
        return state

    def resume(self) -> EmergencyState:
        state = EmergencyState(
            level=EmergencyLevel.NORMAL.value,
            cancel_orders=False,
            disable_new_orders=False,
            freeze_agents=False,
            timestamp=self._get_timestamp(),
        )
        self._record_state(state)
        return state

    def get_current_state(self) -> EmergencyState:
        return self.current_state

    def can_place_orders(self) -> bool:
        return not self.current_state.disable_new_orders

    def should_cancel_orders(self) -> bool:
        return self.current_state.cancel_orders

    def should_freeze_agents(self) -> bool:
        return self.current_state.freeze_agents

    def get_state_history(self, count: int = 20) -> List[EmergencyState]:
        return self.state_history[-count:]

    def _get_timestamp(self) -> int:
        import time
        return int(time.time())
