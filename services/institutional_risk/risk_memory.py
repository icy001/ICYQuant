"""RiskMemory — persistent risk event memory.

Records risk events for audit trail, pattern recognition,
and model improvement over time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RiskMemoryEntry:
    """A single risk memory entry."""

    timestamp: float = 0.0
    event_type: str = ""
    entity_id: str = ""
    severity: str = "LOW"
    metrics: Dict[str, float] = field(default_factory=dict)
    description: str = ""
    snapshot: Optional[Dict[str, Any]] = None


class RiskMemory:
    """Persistent risk event memory.

    Stores risk events for:
    - Audit trail
    - Pattern recognition
    - Model calibration
    - Historical analysis

    Usage::

        memory = RiskMemory(max_entries=10000)
        memory.record(
            event_type="BUDGET_BREACH",
            entity_id="strat_A",
            severity="HIGH",
            metrics={"usage_pct": 112.0, "budget": 2_000_000},
        )
    """

    def __init__(self, max_entries: int = 10000):
        self._entries: List[RiskMemoryEntry] = []
        self._max_entries = max_entries
        self._indices: Dict[str, List[int]] = {}

    def record(
        self,
        event_type: str,
        entity_id: str = "",
        severity: str = "LOW",
        metrics: Optional[Dict[str, float]] = None,
        description: str = "",
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> RiskMemoryEntry:
        """Record a risk event."""
        entry = RiskMemoryEntry(
            timestamp=time.time(),
            event_type=event_type,
            entity_id=entity_id,
            severity=severity,
            metrics=metrics or {},
            description=description,
            snapshot=snapshot,
        )
        self._entries.append(entry)

        # index
        idx = len(self._entries) - 1
        self._indices.setdefault(event_type, []).append(idx)
        if entity_id:
            self._indices.setdefault(f"entity:{entity_id}", []).append(idx)

        # trim
        while len(self._entries) > self._max_entries:
            self._entries.pop(0)
            # rebuild indices (simple approach)
            self._indices.clear()

        return entry

    def query(
        self,
        event_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[RiskMemoryEntry]:
        """Query risk memory.

        Args:
            event_type: filter by event type
            entity_id: filter by entity
            severity: filter by severity
            limit: max results
        """
        results = []

        for entry in reversed(self._entries):
            if event_type and entry.event_type != event_type:
                continue
            if entity_id and entry.entity_id != entity_id:
                continue
            if severity and entry.severity != severity:
                continue
            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def count_by_type(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict[str, int]:
        """Count events by type in a time range."""
        counts: Dict[str, int] = {}
        for entry in self._entries:
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
            counts[entry.event_type] = counts.get(entry.event_type, 0) + 1
        return counts

    def get_latest(self, event_type: str, n: int = 10) -> List[RiskMemoryEntry]:
        """Get the latest N events of a given type."""
        typed = [e for e in self._entries if e.event_type == event_type]
        return typed[-n:]

    def clear(self) -> None:
        """Clear all memory."""
        self._entries.clear()
        self._indices.clear()

    def __len__(self) -> int:
        return len(self._entries)
