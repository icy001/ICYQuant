"""
Decision Registry — Persistent registry for all autonomous decisions.

Stores and indexes all DecisionRecords for querying, lineage
reconstruction, and audit purposes.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DecisionRegistry:
    """
    Registry for all autonomous decisions processed by the Control Plane.

    Provides indexed lookup by decision_id, entity_type, entity_id,
    status, and time range.
    """

    def __init__(self, max_records: int = 1_000_000):
        self._records: dict[str, object] = {}
        self._by_entity_type: dict[str, list[str]] = {}
        self._by_entity_id: dict[str, list[str]] = {}
        self._by_status: dict[str, list[str]] = {}
        self._max_records = max_records

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, record) -> None:
        """Add a decision record to the registry."""
        if len(self._records) >= self._max_records:
            logger.warning("DecisionRegistry at capacity (%d), dropping oldest", self._max_records)
            self._evict_oldest()

        rid = record.decision_id
        self._records[rid] = record

        # Index
        etype = getattr(record, "entity_type", "unknown")
        self._by_entity_type.setdefault(etype, []).append(rid)

        eid = getattr(record, "entity_id", "")
        if eid:
            self._by_entity_id.setdefault(eid, []).append(rid)

        status = getattr(record, "final_status", "unknown")
        self._by_status.setdefault(status, []).append(rid)

    def _evict_oldest(self):
        """Remove the oldest record."""
        if self._records:
            oldest_id = min(
                self._records.keys(),
                key=lambda k: getattr(self._records[k], "timestamp", 0),
            )
            self.remove(oldest_id)

    def remove(self, decision_id: str) -> None:
        """Remove a decision record from the registry."""
        record = self._records.pop(decision_id, None)
        if not record:
            return
        etype = getattr(record, "entity_type", "unknown")
        eid = getattr(record, "entity_id", "")
        status = getattr(record, "final_status", "unknown")
        for idx_map, key in [
            (self._by_entity_type, etype),
            (self._by_entity_id, eid),
            (self._by_status, status),
        ]:
            lst = idx_map.get(key, [])
            if decision_id in lst:
                lst.remove(decision_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, decision_id: str):
        """Get a specific decision record."""
        return self._records.get(decision_id)

    def query(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Query decision records by various criteria."""
        candidates: set[str] = set()

        if entity_type:
            candidates = set(self._by_entity_type.get(entity_type, []))
        elif entity_id:
            candidates = set(self._by_entity_id.get(entity_id, []))
        elif status:
            candidates = set(self._by_status.get(status, []))
        else:
            candidates = set(self._records.keys())

        # Intersect additional filters
        if entity_type and entity_id:
            candidates &= set(self._by_entity_id.get(entity_id, []))
        if status:
            candidates &= set(self._by_status.get(status, []))

        results = [self._records[rid] for rid in list(candidates)[:limit]]
        results.sort(key=lambda r: getattr(r, "timestamp", 0), reverse=True)
        return results

    def count_by_status(self) -> dict:
        return {k: len(v) for k, v in self._by_status.items()}

    def count_by_entity_type(self) -> dict:
        return {k: len(v) for k, v in self._by_entity_type.items()}

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "total_records": len(self._records),
            "by_status": self.count_by_status(),
            "by_entity_type": self.count_by_entity_type(),
            "max_records": self._max_records,
        }
