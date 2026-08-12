"""
KillSwitchRepository — persistent audit trail of kill switch lifecycles.

Stores every kill switch entry (scope / state / reason / actor) plus every
KILL_SWITCH_ACTIVATED / KILL_SWITCH_RELEASED event, so the full lifecycle

    INACTIVE → ACTIVATED → ACTIVE → RELEASE_REQUESTED → RELEASED → INACTIVE

remains auditable (spec section 37).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class KillSwitchRepository:
    """In-memory store of kill switch entries and lifecycle events."""

    _entries: List[Dict[str, Any]] = field(default_factory=list)
    _events: List[Any] = field(default_factory=list)

    # -- writes ----------------------------------------------------------

    def save_entry(self, entry: KillSwitchEntry) -> None:
        self._entries.append(entry.to_dict())

    def append_event(self, event: Any) -> None:
        self._events.append(event)

    # -- queries ---------------------------------------------------------

    def list_entries(self) -> List[KillSwitchEntry]:
        return [KillSwitchEntry.from_dict(e) for e in self._entries]

    def entry_count(self) -> int:
        return len(self._entries)

    def list_active(self) -> List[KillSwitchEntry]:
        return [e for e in self.list_entries() if e.is_blocking]

    def list_events(self) -> List[Any]:
        return list(self._events)

    def event_count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._entries.clear()
        self._events.clear()
