"""Cross-Asset Memory.

Persistent storage and retrieval of cross-asset intelligence analysis
results. Maintains historical records of relationships, signals, risk
assessments, and rotation events for trend analysis and backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class CrossAssetMemoryEntry:
    """A stored cross-asset analysis entry.

    Attributes:
        entry_id: Unique entry identifier.
        entry_type: Type of stored data (signal, risk, rotation, analysis).
        timestamp: When the entry was created.
        data: Stored analysis data.
        tags: Classification tags.
        expires_at: Optional expiration time.
        metadata: Additional context.
    """

    entry_id: str = ""
    entry_type: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def age_hours(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds() / 3600


class CrossAssetMemory:
    """Persistent memory for cross-asset intelligence results.

    Provides storage, query, and retrieval capabilities for historical
    cross-asset analysis including signals, risk assessments, rotation
    events, and relationship graphs.

    Attributes:
        entries: All stored entries indexed by ID.
        type_index: Entries indexed by type.
        tag_index: Entries indexed by tag.
        max_entries: Maximum stored entries before pruning.
        default_ttl_hours: Default time-to-live for entries.
    """

    def __init__(self) -> None:
        self.entries: dict[str, CrossAssetMemoryEntry] = {}
        self.type_index: dict[str, list[str]] = {}
        self.tag_index: dict[str, list[str]] = {}
        self.max_entries: int = 10000
        self.default_ttl_hours: int = 168
        self._id_counter: int = 0

    def store(self, entry_type: str, data: dict[str, Any],
              tags: list[str] | None = None,
              ttl_hours: int | None = None,
              metadata: dict[str, Any] | None = None) -> CrossAssetMemoryEntry:
        self._id_counter += 1
        entry_id = f"CA-{self._id_counter:08d}"

        expires_at = None
        if ttl_hours is not None:
            expires_at = datetime.now() + timedelta(hours=ttl_hours)
        elif self.default_ttl_hours > 0:
            expires_at = datetime.now() + timedelta(hours=self.default_ttl_hours)

        entry = CrossAssetMemoryEntry(
            entry_id=entry_id,
            entry_type=entry_type,
            data=data,
            tags=tags or [],
            expires_at=expires_at,
            metadata=metadata or {},
        )

        self.entries[entry_id] = entry

        if entry_type not in self.type_index:
            self.type_index[entry_type] = []
        self.type_index[entry_type].append(entry_id)

        for tag in entry.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            self.tag_index[tag].append(entry_id)

        if len(self.entries) > self.max_entries:
            self._prune()

        return entry

    def store_signal(self, signal_data: dict[str, Any],
                     tags: list[str] | None = None) -> CrossAssetMemoryEntry:
        return self.store("signal", signal_data, tags=tags)

    def store_risk(self, risk_data: dict[str, Any],
                   tags: list[str] | None = None) -> CrossAssetMemoryEntry:
        return self.store("risk", risk_data, tags=tags)

    def store_rotation(self, rotation_data: dict[str, Any],
                       tags: list[str] | None = None) -> CrossAssetMemoryEntry:
        return self.store("rotation", rotation_data, tags=tags)

    def store_analysis(self, analysis_data: dict[str, Any],
                       tags: list[str] | None = None) -> CrossAssetMemoryEntry:
        return self.store("analysis", analysis_data, tags=tags)

    def get(self, entry_id: str) -> CrossAssetMemoryEntry | None:
        entry = self.entries.get(entry_id)
        if entry and entry.is_expired:
            self.delete(entry_id)
            return None
        return entry

    def query_by_type(self, entry_type: str, limit: int = 50) -> list[CrossAssetMemoryEntry]:
        ids = self.type_index.get(entry_type, [])
        entries = [self.entries[i] for i in ids if i in self.entries and not self.entries[i].is_expired]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def query_by_tag(self, tag: str, limit: int = 50) -> list[CrossAssetMemoryEntry]:
        ids = self.tag_index.get(tag, [])
        entries = [self.entries[i] for i in ids if i in self.entries and not self.entries[i].is_expired]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def query_recent(self, hours: int = 24, entry_type: str | None = None,
                     limit: int = 100) -> list[CrossAssetMemoryEntry]:
        cutoff = datetime.now() - timedelta(hours=hours)
        source = list(self.entries.values())
        if entry_type:
            ids = self.type_index.get(entry_type, [])
            source = [self.entries[i] for i in ids if i in self.entries]
        recent = [e for e in source if e.timestamp >= cutoff and not e.is_expired]
        recent.sort(key=lambda e: e.timestamp, reverse=True)
        return recent[:limit]

    def query_range(self, start: datetime, end: datetime | None = None,
                    entry_type: str | None = None,
                    limit: int = 200) -> list[CrossAssetMemoryEntry]:
        end_time = end or datetime.now()
        ids = self.type_index.get(entry_type, []) if entry_type else list(self.entries.keys())
        entries = [
            self.entries[i] for i in ids
            if i in self.entries
            and start <= self.entries[i].timestamp <= end_time
            and not self.entries[i].is_expired
        ]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def get_signal_history(self, target_asset: str | None = None,
                           hours: int = 72) -> list[dict[str, Any]]:
        signals = self.query_by_type("signal", limit=200)
        cutoff = datetime.now() - timedelta(hours=hours)
        result: list[dict[str, Any]] = []
        for s in signals:
            if s.timestamp < cutoff:
                continue
            if target_asset and s.data.get("target_asset") != target_asset:
                continue
            d = dict(s.data)
            d["timestamp"] = s.timestamp.isoformat()
            result.append(d)
        return result

    def get_risk_history(self, hours: int = 72) -> list[dict[str, Any]]:
        risks = self.query_by_type("risk", limit=100)
        cutoff = datetime.now() - timedelta(hours=hours)
        result: list[dict[str, Any]] = []
        for r in risks:
            if r.timestamp < cutoff:
                continue
            d = dict(r.data)
            d["timestamp"] = r.timestamp.isoformat()
            result.append(d)
        return result

    def get_regime_history(self, hours: int = 168) -> list[str]:
        entries = self.query_recent(hours=hours, entry_type=None, limit=500)
        regimes: list[tuple[datetime, str]] = []
        for e in entries:
            regime = e.data.get("regime") or e.data.get("current_regime")
            if regime:
                regimes.append((e.timestamp, str(regime)))
        regimes.sort(key=lambda x: x[0])
        return [r[1] for r in regimes]

    def get_stats(self) -> dict[str, Any]:
        total = len(self.entries)
        type_counts = {t: len(ids) for t, ids in self.type_index.items()}
        tag_counts: dict[str, int] = {}
        for tag, ids in self.tag_index.items():
            count = sum(1 for i in ids if i in self.entries and not self.entries[i].is_expired)
            if count > 0:
                tag_counts[tag] = count
        return {
            "total_entries": total,
            "active_entries": sum(1 for e in self.entries.values() if not e.is_expired),
            "type_distribution": type_counts,
            "tag_distribution": tag_counts,
            "max_entries": self.max_entries,
        }

    def cleanup_expired(self) -> int:
        expired_ids = [eid for eid, e in self.entries.items() if e.is_expired]
        for eid in expired_ids:
            self.delete(eid)
        return len(expired_ids)

    def delete(self, entry_id: str) -> bool:
        entry = self.entries.pop(entry_id, None)
        if entry is None:
            return False
        if entry.entry_type in self.type_index:
            ids = self.type_index[entry.entry_type]
            if entry_id in ids:
                ids.remove(entry_id)
        for tag in entry.tags:
            if tag in self.tag_index:
                ids = self.tag_index[tag]
                if entry_id in ids:
                    ids.remove(entry_id)
        return True

    def _prune(self) -> None:
        self.cleanup_expired()
        if len(self.entries) <= self.max_entries:
            return
        sorted_entries = sorted(self.entries.values(), key=lambda e: e.timestamp)
        remove_count = len(self.entries) - self.max_entries + int(self.max_entries * 0.1)
        for entry in sorted_entries[:remove_count]:
            self.delete(entry.entry_id)

    def clear(self) -> None:
        self.entries.clear()
        self.type_index.clear()
        self.tag_index.clear()
        self._id_counter = 0
