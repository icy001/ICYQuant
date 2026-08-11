"""
Capacity Runtime — Live capacity monitoring and runtime state management.

Provides real-time capacity state tracking, dynamic updates based on
market conditions, and integration with the execution pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .capacity_intelligence import CapacityState


class RuntimeEvent(str, Enum):
    CAPACITY_ASSESSED = "capacity_assessed"
    CAPACITY_DEGRADED = "capacity_degraded"
    CAPACITY_RESTORED = "capacity_restored"
    CAPACITY_FROZEN = "capacity_frozen"
    MARKET_REGIME_CHANGE = "market_regime_change"
    LIQUIDITY_CHANGE = "liquidity_change"


@dataclass
class RuntimeState:
    """Current runtime capacity state for a strategy/asset pair."""

    strategy_id: str = ""
    asset: str = ""
    current_state: CapacityState = CapacityState.AVAILABLE
    executable_capital: float = 0.0
    max_capacity: float = float("inf")
    last_assessed: str = ""
    events_since_reset: int = 0
    degraded_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "state": self.current_state.value,
            "executable_capital": self.executable_capital,
            "max_capacity": self.max_capacity,
            "degraded_count": self.degraded_count,
        }


class CapacityRuntime:
    """Manages live capacity state and dynamic updates."""

    def __init__(self):
        self._states: Dict[str, RuntimeState] = {}  # key: "strategy_id:asset"
        self._event_log: List[Tuple[str, RuntimeEvent, Dict[str, Any]]] = []
        self._frozen: bool = False

    def _key(self, strategy_id: str, asset: str) -> str:
        return f"{strategy_id}:{asset}"

    def get(self, strategy_id: str, asset: str = "") -> Optional[RuntimeState]:
        key = self._key(strategy_id, asset)
        return self._states.get(key)

    def update(
        self,
        strategy_id: str,
        asset: str,
        state: CapacityState,
        executable_capital: float,
        max_capacity: float = float("inf"),
    ) -> RuntimeState:
        key = self._key(strategy_id, asset)
        if key not in self._states:
            self._states[key] = RuntimeState(strategy_id=strategy_id, asset=asset)

        rs = self._states[key]
        old_state = rs.current_state
        rs.current_state = state
        rs.executable_capital = executable_capital
        rs.max_capacity = max_capacity
        rs.last_assessed = datetime.now(timezone.utc).isoformat()
        rs.events_since_reset += 1

        if state == CapacityState.DEGRADED:
            rs.degraded_count += 1
            self._log_event(strategy_id, RuntimeEvent.CAPACITY_DEGRADED, {"asset": asset, "previous": old_state.value})

        if state == CapacityState.FROZEN:
            self._log_event(strategy_id, RuntimeEvent.CAPACITY_FROZEN, {"asset": asset})

        return rs

    def degrade(self, strategy_id: str, asset: str, reason: str = "") -> RuntimeState:
        rs = self.get(strategy_id, asset)
        if rs:
            return self.update(strategy_id, asset, CapacityState.DEGRADED, rs.executable_capital * 0.5, rs.max_capacity)
        return self.update(strategy_id, asset, CapacityState.DEGRADED, 0.0)

    def restore(self, strategy_id: str, asset: str) -> Optional[RuntimeState]:
        rs = self.get(strategy_id, asset)
        if rs:
            self._log_event(strategy_id, RuntimeEvent.CAPACITY_RESTORED, {"asset": asset})
            rs.current_state = CapacityState.EXECUTABLE
            rs.events_since_reset = 0
        return rs

    def freeze_all(self) -> None:
        self._frozen = True
        for key, rs in self._states.items():
            rs.current_state = CapacityState.FROZEN
        self._log_event("GLOBAL", RuntimeEvent.CAPACITY_FROZEN, {"scope": "all"})

    def unfreeze_all(self) -> None:
        self._frozen = False
        for key, rs in self._states.items():
            rs.current_state = CapacityState.AVAILABLE

    def all_states(self) -> List[RuntimeState]:
        return list(self._states.values())

    def degraded_strategies(self) -> List[str]:
        return list(set(rs.strategy_id for rs in self._states.values() if rs.current_state == CapacityState.DEGRADED))

    def _log_event(self, strategy_id: str, event: RuntimeEvent, detail: Dict[str, Any]) -> None:
        self._event_log.append((strategy_id, event, detail))

    def recent_events(self, n: int = 50) -> List[Tuple[str, RuntimeEvent, Dict[str, Any]]]:
        return self._event_log[-n:]

    def summary(self) -> Dict[str, Any]:
        states = self.all_states()
        if not states:
            return {"tracked": 0}
        return {
            "tracked": len(states),
            "frozen": self._frozen,
            "executable": sum(1 for s in states if s.current_state == CapacityState.EXECUTABLE),
            "degraded": sum(1 for s in states if s.current_state == CapacityState.DEGRADED),
            "frozen_count": sum(1 for s in states if s.current_state == CapacityState.FROZEN),
            "total_executable_capital": sum(s.executable_capital for s in states),
        }
