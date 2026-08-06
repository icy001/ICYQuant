"""Trigger Manager — lifecycle, activation, and statistics for all triggers.

The :class:`TriggerManager` tracks every trigger instance registered with
the engine.  It manages enable/disable, statistics collection, and provides
the active-trigger list to the evaluation loop.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TriggerManagerState:
    """Manager lifecycle states."""

    UNINITIALIZED = "uninitialized"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass
class _TriggerEntry:
    """Internal bookkeeping for a registered trigger."""

    trigger: Any
    trigger_id: str
    enabled: bool = True
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_evaluated_at: Optional[datetime] = None
    last_fired_at: Optional[datetime] = None
    total_fired: int = 0
    total_misfired: int = 0
    total_errors: int = 0


class TriggerManager:
    """Lifecycle manager for all trigger instances.

    Responsibilities:
    * Registration / unregistration
    * Enable / disable (dynamic toggling at runtime)
    * Statistics collection per trigger
    * Providing the active-trigger list for evaluation loops
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: str = TriggerManagerState.UNINITIALIZED
        self._entries: Dict[str, _TriggerEntry] = {}

    async def start(self) -> None:
        with self._lock:
            self._state = TriggerManagerState.RUNNING

    async def stop(self) -> None:
        with self._lock:
            self._state = TriggerManagerState.STOPPED
            self._entries.clear()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, trigger: Any) -> str:
        trigger_id = getattr(trigger, "trigger_id", f"trigger_{id(trigger):x}")
        with self._lock:
            self._entries[trigger_id] = _TriggerEntry(
                trigger=trigger, trigger_id=trigger_id
            )
        return trigger_id

    async def unregister(self, trigger_id: str) -> None:
        with self._lock:
            self._entries.pop(trigger_id, None)

    async def enable(self, trigger_id: str) -> None:
        with self._lock:
            entry = self._entries.get(trigger_id)
            if entry:
                entry.enabled = True

    async def disable(self, trigger_id: str) -> None:
        with self._lock:
            entry = self._entries.get(trigger_id)
            if entry:
                entry.enabled = False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_active_triggers(self) -> List[Any]:
        """Return the list of enabled trigger instances for evaluation."""
        with self._lock:
            return [e.trigger for e in self._entries.values() if e.enabled]

    def list_triggers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "trigger_id": e.trigger_id,
                    "enabled": e.enabled,
                    "registered_at": e.registered_at.isoformat(),
                    "last_evaluated_at": (
                        e.last_evaluated_at.isoformat() if e.last_evaluated_at else None
                    ),
                    "last_fired_at": (
                        e.last_fired_at.isoformat() if e.last_fired_at else None
                    ),
                    "total_fired": e.total_fired,
                    "total_misfired": e.total_misfired,
                    "total_errors": e.total_errors,
                }
                for e in self._entries.values()
            ]

    def get_trigger_count(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Stats recording (called by engine loop)
    # ------------------------------------------------------------------

    def record_evaluation(self, trigger_id: str) -> None:
        with self._lock:
            entry = self._entries.get(trigger_id)
            if entry:
                entry.last_evaluated_at = datetime.now(timezone.utc)

    def record_fired(self, trigger_id: str) -> None:
        with self._lock:
            entry = self._entries.get(trigger_id)
            if entry:
                entry.last_fired_at = datetime.now(timezone.utc)
                entry.total_fired += 1

    def record_misfire(self, trigger_id: str) -> None:
        with self._lock:
            entry = self._entries.get(trigger_id)
            if entry:
                entry.total_misfired += 1

    def record_error(self, trigger_id: str) -> None:
        with self._lock:
            entry = self._entries.get(trigger_id)
            if entry:
                entry.total_errors += 1

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "total_triggers": len(self._entries),
                "enabled": sum(1 for e in self._entries.values() if e.enabled),
                "disabled": sum(1 for e in self._entries.values() if not e.enabled),
            }
