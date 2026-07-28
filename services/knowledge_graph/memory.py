"""Graph Memory – stores graph versions, entity history, and relationship history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class GraphMemory:
    """Stores versions of the knowledge graph, entity history, and relationship changes.

    Forms the Knowledge History for audit and rollback.
    """

    def __init__(self) -> None:
        self.versions: List[Dict[str, Any]] = []
        self._entity_history: List[Dict[str, Any]] = []
        self._relation_history: List[Dict[str, Any]] = []
        self._event_history: List[Dict[str, Any]] = []
        self._version_counter: int = 0

    def save(self, version: Dict[str, Any]) -> str:
        """Save a graph version snapshot.

        Args:
            version: graph state dict.

        Returns:
            Version id string.
        """
        self._version_counter += 1
        version_id = f"v{self._version_counter}"
        record = {
            "version_id": version_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": version,
        }
        self.versions.append(record)
        return version_id

    def save_snapshot(self, node_count: int, edge_count: int, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Save a lightweight version snapshot."""
        return self.save({
            "node_count": node_count,
            "edge_count": edge_count,
            "metadata": metadata or {},
        })

    def record_entity(self, action: str, entity_id: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record an entity change event."""
        self._entity_history.append({
            "action": action,
            "entity_id": entity_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_relation(
        self,
        action: str,
        source: str,
        target: str,
        relation: str,
    ) -> None:
        """Record a relationship change event."""
        self._relation_history.append({
            "action": action,
            "source": source,
            "target": target,
            "relation": relation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_event(self, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a propagation or causal event."""
        self._event_history.append({
            "type": event_type,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_versions(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent N snapshots."""
        return self.versions[-n:]

    def get_latest_version(self) -> Optional[Dict[str, Any]]:
        """Return the most recent snapshot."""
        return self.versions[-1] if self.versions else None

    def get_entity_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """Return change history for a specific entity."""
        return [h for h in self._entity_history if h["entity_id"] == entity_id]

    def get_relation_history(self, relation: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return relation change history, optionally filtered."""
        if relation:
            return [h for h in self._relation_history if h["relation"] == relation]
        return list(self._relation_history)

    @property
    def version_count(self) -> int:
        return len(self.versions)

    @property
    def entity_history_count(self) -> int:
        return len(self._entity_history)

    @property
    def relation_history_count(self) -> int:
        return len(self._relation_history)

    @property
    def event_history_count(self) -> int:
        return len(self._event_history)

    def clear(self) -> None:
        self.versions.clear()
        self._entity_history.clear()
        self._relation_history.clear()
        self._event_history.clear()
        self._version_counter = 0
