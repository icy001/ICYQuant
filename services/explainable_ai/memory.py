"""Explainable Memory – persistent storage for explanations and knowledge base."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ExplainableMemory:
    """Stores explanations, feature importance, confidence scores, and audit records.

    Forms the Explainable Knowledge Base for future retrieval and analysis.
    """

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Save an explanation record.

        Args:
            record: explanation record with arbitrary fields.

        Returns:
            The saved record with timestamp added.
        """
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.records.append(record)
        return record

    def query_by_strategy(self, strategy: str) -> List[Dict[str, Any]]:
        """Retrieve all records for a given strategy."""
        return [r for r in self.records if r.get("strategy") == strategy]

    def query_by_signal(self, signal: str) -> List[Dict[str, Any]]:
        """Retrieve all records for a given signal."""
        return [r for r in self.records if r.get("signal") == signal]

    def query_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent N records."""
        sorted_records = sorted(
            self.records,
            key=lambda r: r.get("timestamp", ""),
            reverse=True,
        )
        return sorted_records[:n]

    def clear(self) -> None:
        """Clear all stored records."""
        self.records.clear()

    @property
    def record_count(self) -> int:
        return len(self.records)
