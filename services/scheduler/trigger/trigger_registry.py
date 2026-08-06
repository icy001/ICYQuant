"""Trigger Registry — typed registration and discovery of trigger instances.

The :class:`TriggerRegistry` stores every trigger by id and supports
lookup by schedule, type, and state.  It is the source-of-truth for
"which triggers exist".
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TriggerRegistry:
    """In-memory registry of all trigger instances.

    Supports:
    * Registration / unregistration
    * Lookup by trigger_id, schedule_id, trigger_type
    * Version tracking (timestamp-based)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._triggers: Dict[str, Any] = {}
        self._by_schedule: Dict[str, List[str]] = {}
        self._by_type: Dict[str, List[str]] = {}
        self._version: int = 0

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, trigger: Any) -> str:
        trigger_id = getattr(trigger, "trigger_id", f"trigger_{id(trigger):x}")
        schedule_id = getattr(trigger, "schedule_id", "")
        trigger_type = getattr(trigger, "trigger_type", "unknown")

        with self._lock:
            self._triggers[trigger_id] = trigger
            self._by_schedule.setdefault(schedule_id, []).append(trigger_id)
            self._by_type.setdefault(str(trigger_type), []).append(trigger_id)
            self._version += 1
        return trigger_id

    def unregister(self, trigger_id: str) -> bool:
        with self._lock:
            trigger = self._triggers.pop(trigger_id, None)
            if trigger is None:
                return False
            schedule_id = getattr(trigger, "schedule_id", "")
            trigger_type = str(getattr(trigger, "trigger_type", "unknown"))
            if schedule_id in self._by_schedule:
                self._by_schedule[schedule_id] = [
                    t for t in self._by_schedule[schedule_id] if t != trigger_id
                ]
            if trigger_type in self._by_type:
                self._by_type[trigger_type] = [
                    t for t in self._by_type[trigger_type] if t != trigger_id
                ]
            self._version += 1
            return True

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, trigger_id: str) -> Optional[Any]:
        with self._lock:
            return self._triggers.get(trigger_id)

    def get_by_schedule(self, schedule_id: str) -> List[Any]:
        with self._lock:
            ids = self._by_schedule.get(schedule_id, [])
            return [self._triggers[tid] for tid in ids if tid in self._triggers]

    def get_by_type(self, trigger_type: str) -> List[Any]:
        with self._lock:
            ids = self._by_type.get(trigger_type, [])
            return [self._triggers[tid] for tid in ids if tid in self._triggers]

    def list_all(self) -> List[Any]:
        with self._lock:
            return list(self._triggers.values())

    def count(self) -> int:
        return len(self._triggers)

    @property
    def version(self) -> int:
        return self._version

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_triggers": len(self._triggers),
                "by_type": {k: len(v) for k, v in self._by_type.items()},
                "version": self._version,
            }
