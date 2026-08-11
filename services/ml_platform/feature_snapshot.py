"""
ICYQuant Feature Snapshot - Immutable feature data snapshots.

A Feature Snapshot captures the complete computed state of a set of
features at a specific point in time. Snapshots are immutable and
serve as the foundation for reproducible research and auditing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FeatureSnapshot:
    """Immutable snapshot of computed feature data.

    Captures everything needed to reproduce or audit a feature state:
    - What features were computed (feature_ids + versions)
    - When they were computed (timestamp)
    - Actual data (reference to stored data)
    - Metadata (entities, date range, row count)
    - Hash for integrity verification
    """

    snapshot_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Features included
    feature_ids: List[str] = field(default_factory=list)
    feature_versions: Dict[str, str] = field(default_factory=dict)  # feature_id -> version_id

    # Data reference
    data_path: str = ""         # path to stored data (parquet, etc.)
    data_format: str = "parquet"
    data_hash: str = ""         # SHA256 of data for integrity

    # Scope
    entity_ids: List[str] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Statistics
    entity_count: int = 0
    row_count: int = 0
    column_count: int = 0
    null_ratio: float = 0.0
    data_size_bytes: int = 0

    # Reproducibility
    code_version: str = ""          # git commit
    environment_hash: str = ""      # dependencies hash
    pipeline_run_id: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    description: str = ""

    def compute_data_hash(self) -> str:
        """Compute hash for integrity verification."""
        content = {
            "feature_ids": sorted(self.feature_ids),
            "versions": sorted(self.feature_versions.items()),
            "entity_ids": sorted(self.entity_ids),
            "start_date": self.start_date.isoformat() if self.start_date else "",
            "end_date": self.end_date.isoformat() if self.end_date else "",
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


class SnapshotManager:
    """Manages feature snapshots.

    Snapshots are immutable once created. They cannot be modified
    or deleted to ensure audit trail integrity.
    """

    def __init__(self) -> None:
        self._snapshots: Dict[str, FeatureSnapshot] = {}
        self._feature_snapshots: Dict[str, List[str]] = {}  # feature_id -> [snapshot_ids]

    def create(self, snapshot: FeatureSnapshot) -> str:
        """Create and store an immutable snapshot."""
        snapshot.data_hash = snapshot.compute_data_hash()
        self._snapshots[snapshot.snapshot_id] = snapshot

        # Index by feature
        for feature_id in snapshot.feature_ids:
            if feature_id not in self._feature_snapshots:
                self._feature_snapshots[feature_id] = []
            self._feature_snapshots[feature_id].append(snapshot.snapshot_id)

        logger.info("Snapshot created: %s (%d features, %d rows)",
                     snapshot.snapshot_id, len(snapshot.feature_ids), snapshot.row_count)
        return snapshot.snapshot_id

    def get(self, snapshot_id: str) -> Optional[FeatureSnapshot]:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def get_snapshots_for_feature(self, feature_id: str) -> List[FeatureSnapshot]:
        """Get all snapshots containing a specific feature."""
        snapshot_ids = self._feature_snapshots.get(feature_id, [])
        return [self._snapshots[sid] for sid in snapshot_ids if sid in self._snapshots]

    def get_latest_snapshot(self, feature_ids: Optional[List[str]] = None) -> Optional[FeatureSnapshot]:
        """Get the most recent snapshot (optionally filtered by feature)."""
        candidates = list(self._snapshots.values())
        if feature_ids:
            candidates = [
                s for s in candidates
                if all(fid in s.feature_ids for fid in feature_ids)
            ]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.created_at)

    def list_snapshots(self, limit: int = 50) -> List[FeatureSnapshot]:
        """List recent snapshots."""
        sorted_snapshots = sorted(
            self._snapshots.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return sorted_snapshots[:limit]

    def compare_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> Dict[str, Any]:
        """Compare two snapshots to identify changes."""
        sa = self._snapshots.get(snapshot_id_a)
        sb = self._snapshots.get(snapshot_id_b)
        if not sa or not sb:
            return {"error": "Snapshot not found"}

        return {
            "snapshot_a": snapshot_id_a,
            "snapshot_b": snapshot_id_b,
            "time_between": str(sb.created_at - sa.created_at) if sa and sb else "",
            "features_added": list(set(sb.feature_ids) - set(sa.feature_ids)) if sa and sb else [],
            "features_removed": list(set(sa.feature_ids) - set(sb.feature_ids)) if sa and sb else [],
            "entity_count_change": (sb.entity_count - sa.entity_count) if sa and sb else 0,
            "row_count_change": (sb.row_count - sa.row_count) if sa and sb else 0,
        }

    @property
    def count(self) -> int:
        return len(self._snapshots)
