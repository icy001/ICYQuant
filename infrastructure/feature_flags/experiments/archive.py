"""
Experiment archive.

Archives completed experiments for
historical reference and audit purposes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from .experiment import Experiment


class ExperimentArchive:
    """
    Archive for completed experiments.

    Stores experiment configurations, results,
    and metadata for historical reference.

    Usage:
        archive = ExperimentArchive()
        await archive.store(experiment, result={"winner": "treatment"})
        entry = await archive.retrieve("exp-123")
    """

    def __init__(self, max_entries: int = 5000) -> None:
        """
        Initialize the archive.

        Args:
            max_entries: Maximum archived entries.
        """
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
        self._archive_count = 0

    async def store(
        self,
        experiment: Experiment,
        result: Optional[Dict[str, Any]] = None,
        operator: str = "system",
    ) -> Dict[str, Any]:
        """
        Archive a completed experiment.

        Args:
            experiment: Experiment to archive.
            result: Analysis results.
            operator: Who archived the experiment.

        Returns:
            The archive entry.
        """
        entry = {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "feature_key": experiment.feature_key,
            "status": experiment.status,
            "winner_variant_id": experiment.winner_variant_id,
            "variants": [
                v.to_dict() if hasattr(v, "to_dict") else v
                for v in experiment.variants
            ],
            "traffic_percentage": experiment.traffic_percentage,
            "result": result or {},
            "operator": operator,
            "archived_at": datetime.utcnow().isoformat(),
            "metadata": experiment.metadata,
        }

        async with self._lock:
            self._entries[experiment.experiment_id] = entry
            self._archive_count += 1
            # Evict if over limit
            if len(self._entries) > self._max_entries:
                keys = list(self._entries.keys())
                for k in keys[: len(keys) - self._max_entries]:
                    del self._entries[k]

        return entry

    async def retrieve(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an archived experiment.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            Archive entry or None.
        """
        return self._entries.get(experiment_id)

    async def query(
        self,
        feature_key: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query archived experiments.

        Args:
            feature_key: Filter by feature key.
            limit: Max entries to return.

        Returns:
            List of archive entries.
        """
        entries = list(self._entries.values())
        if feature_key:
            entries = [e for e in entries if e.get("feature_key") == feature_key]
        return list(reversed(entries))[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get archive statistics."""
        return {
            "total_archived": len(self._entries),
            "archive_count": self._archive_count,
            "max_entries": self._max_entries,
        }
