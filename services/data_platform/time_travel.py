"""ICYQuant Data Time Travel.

Point-in-time query capability for all data in the lakehouse.
Allows querying data as it existed at any historical timestamp:

    SELECT * FROM market_tick AS OF '2026-07-28 22:00:00'

Supports:
    - Timestamp-based queries
    - Branch-based data views (main, dev, experiment)
    - Snapshot tagging
    - Historical comparison

Usage::

    tt = TimeTravel(TimeTravelConfig(), lakehouse)
    data = tt.query_as_of("market_tick", datetime(2026, 7, 28, 22, 0))
    tt.create_branch("experiment_v2", from_timestamp=datetime(2026, 7, 28))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.data_platform.config import TimeTravelConfig
from services.data_platform.lakehouse import DataLakehouse, TableSnapshot


# ============================================================================
# Time Travel Types
# ============================================================================


@dataclass
class TimeBranch:
    """A named branch for time-travel data views."""

    name: str
    dataset: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    as_of_timestamp: Optional[datetime] = None
    description: str = ""
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataset": self.dataset,
            "created_at": self.created_at.isoformat(),
            "as_of_timestamp": self.as_of_timestamp.isoformat() if self.as_of_timestamp else None,
            "description": self.description,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


@dataclass
class TimeTag:
    """A named tag pointing to a specific point in time."""

    name: str
    dataset: str
    timestamp: datetime
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataset": self.dataset,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
        }


@dataclass
class TimeTravelResult:
    """Result of a time-travel query."""

    dataset: str
    timestamp: datetime
    data: List[Dict[str, Any]] = field(default_factory=list)
    snapshot_id: str = ""
    is_exact_match: bool = False
    actual_timestamp: Optional[datetime] = None
    row_count: int = 0
    error: str = ""


# ============================================================================
# Time Travel Engine
# ============================================================================


class TimeTravel:
    """Time Travel Engine.

    Enables point-in-time queries, branching, and historical data access.

    Usage::

        tt = TimeTravel(TimeTravelConfig(), lakehouse)
        data = tt.query_as_of("market_tick", datetime(2026, 7, 28))
        tt.tag("daily_close_jul28", "market_tick", datetime(2026, 7, 28, 16, 0))
        tt.create_branch("backtest_2026q3", "market_tick", datetime(2026, 6, 30))
    """

    def __init__(
        self,
        config: Optional[TimeTravelConfig] = None,
        lakehouse: Optional[DataLakehouse] = None,
    ) -> None:
        self.config = config or TimeTravelConfig()
        self.lakehouse = lakehouse
        self._branches: Dict[str, TimeBranch] = {}
        self._tags: Dict[str, TimeTag] = {}

    # ------------------------------------------------------------------
    # Point-in-Time Queries
    # ------------------------------------------------------------------

    def query_as_of(
        self,
        dataset: str,
        timestamp: datetime,
    ) -> TimeTravelResult:
        """Query data as it existed at a specific timestamp.

        Args:
            dataset: Dataset name.
            timestamp: Point-in-time to query.

        Returns:
            TimeTravelResult with historical data.
        """
        if not self.config.enabled:
            return TimeTravelResult(
                dataset=dataset,
                timestamp=timestamp,
                error="Time travel is disabled",
            )

        data: List[Dict[str, Any]] = []
        snapshot_id = ""
        is_exact = False
        actual_ts: Optional[datetime] = None

        if self.lakehouse:
            # Find the closest snapshot at or before the timestamp
            snapshots = self.lakehouse.list_snapshots(dataset)
            valid_snapshots = [s for s in snapshots if s.timestamp <= timestamp]

            if valid_snapshots:
                closest = max(valid_snapshots, key=lambda s: s.timestamp)
                snapshot_id = closest.snapshot_id
                actual_ts = closest.timestamp
                is_exact = (closest.timestamp == timestamp)

            data = self.lakehouse.read(dataset, as_of=timestamp)

        return TimeTravelResult(
            dataset=dataset,
            timestamp=timestamp,
            data=data,
            snapshot_id=snapshot_id,
            is_exact_match=is_exact,
            actual_timestamp=actual_ts,
            row_count=len(data),
        )

    def query_sql_as_of(
        self,
        sql: str,
        timestamp: datetime,
    ) -> TimeTravelResult:
        """Execute a SQL query as of a historical timestamp.

        Args:
            sql: SQL query string.
            timestamp: Point-in-time.

        Returns:
            TimeTravelResult with historical data.
        """
        # Extract dataset from SQL
        parts = sql.strip().split()
        from_idx = next((i for i, p in enumerate(parts) if p.upper() == "FROM"), None)
        dataset = parts[from_idx + 1].rstrip(";") if from_idx else "unknown"

        if self.lakehouse:
            data = self.lakehouse.read_sql(sql, as_of=timestamp)
            return TimeTravelResult(
                dataset=dataset,
                timestamp=timestamp,
                data=data,
                row_count=len(data),
            )

        return TimeTravelResult(dataset=dataset, timestamp=timestamp)

    def compare_versions(
        self,
        dataset: str,
        timestamp_a: datetime,
        timestamp_b: datetime,
    ) -> Dict[str, Any]:
        """Compare data at two different points in time.

        Args:
            dataset: Dataset name.
            timestamp_a: First timestamp.
            timestamp_b: Second timestamp.

        Returns:
            Dict with comparison results.
        """
        result_a = self.query_as_of(dataset, timestamp_a)
        result_b = self.query_as_of(dataset, timestamp_b)

        return {
            "dataset": dataset,
            "timestamp_a": timestamp_a.isoformat(),
            "timestamp_b": timestamp_b.isoformat(),
            "rows_a": result_a.row_count,
            "rows_b": result_b.row_count,
            "delta_rows": result_b.row_count - result_a.row_count,
            "snapshot_a": result_a.snapshot_id,
            "snapshot_b": result_b.snapshot_id,
        }

    # ------------------------------------------------------------------
    # Branching
    # ------------------------------------------------------------------

    def create_branch(
        self,
        name: str,
        dataset: str,
        from_timestamp: Optional[datetime] = None,
        description: str = "",
    ) -> TimeBranch:
        """Create a named branch from a point in time.

        Branches allow parallel data views for experimentation.

        Args:
            name: Branch name.
            dataset: Dataset name.
            from_timestamp: Branch point (defaults to now).
            description: Branch description.

        Returns:
            TimeBranch.
        """
        branch = TimeBranch(
            name=name,
            dataset=dataset,
            as_of_timestamp=from_timestamp,
            description=description,
        )

        branch_key = f"{dataset}:{name}"
        self._branches[branch_key] = branch
        return branch

    def get_branch(self, dataset: str, name: str) -> Optional[TimeBranch]:
        """Get a branch by dataset and name."""
        return self._branches.get(f"{dataset}:{name}")

    def query_branch(
        self, dataset: str, branch_name: str
    ) -> TimeTravelResult:
        """Query data from a specific branch.

        Args:
            dataset: Dataset name.
            branch_name: Branch name.

        Returns:
            TimeTravelResult.
        """
        branch = self.get_branch(dataset, branch_name)
        if not branch:
            return TimeTravelResult(
                dataset=dataset,
                timestamp=datetime.utcnow(),
                error=f"Branch '{branch_name}' not found",
            )

        if branch.as_of_timestamp:
            return self.query_as_of(dataset, branch.as_of_timestamp)

        return self.query_as_of(dataset, datetime.utcnow())

    def list_branches(self, dataset: Optional[str] = None) -> List[TimeBranch]:
        """List all branches, optionally filtered by dataset.

        Args:
            dataset: Filter by dataset.

        Returns:
            List of TimeBranch.
        """
        branches = list(self._branches.values())
        if dataset:
            branches = [b for b in branches if b.dataset == dataset]
        return branches

    def delete_branch(self, dataset: str, name: str) -> bool:
        """Delete a branch.

        Args:
            dataset: Dataset name.
            name: Branch name.

        Returns:
            True if deleted.
        """
        branch_key = f"{dataset}:{name}"
        if branch_key in self._branches:
            del self._branches[branch_key]
            return True
        return False

    # ------------------------------------------------------------------
    # Tagging
    # ------------------------------------------------------------------

    def tag(
        self,
        name: str,
        dataset: str,
        timestamp: datetime,
        description: str = "",
        created_by: str = "system",
    ) -> TimeTag:
        """Create a named tag for a point in time.

        Tags are named references to specific timestamps, useful for
        marking important data states (e.g. "month_end_close").

        Args:
            name: Tag name.
            dataset: Dataset name.
            timestamp: Point-in-time to tag.
            description: Tag description.
            created_by: Who created the tag.

        Returns:
            TimeTag.
        """
        tag = TimeTag(
            name=name,
            dataset=dataset,
            timestamp=timestamp,
            description=description,
            created_by=created_by,
        )

        tag_key = f"{dataset}:{name}"
        self._tags[tag_key] = tag
        return tag

    def get_tag(self, dataset: str, name: str) -> Optional[TimeTag]:
        """Get a tag by dataset and name."""
        return self._tags.get(f"{dataset}:{name}")

    def query_tag(self, dataset: str, tag_name: str) -> TimeTravelResult:
        """Query data at a tagged point in time.

        Args:
            dataset: Dataset name.
            tag_name: Tag name.

        Returns:
            TimeTravelResult.
        """
        tag = self.get_tag(dataset, tag_name)
        if not tag:
            return TimeTravelResult(
                dataset=dataset,
                timestamp=datetime.utcnow(),
                error=f"Tag '{tag_name}' not found",
            )

        return self.query_as_of(dataset, tag.timestamp)

    def list_tags(self, dataset: Optional[str] = None) -> List[TimeTag]:
        """List all tags, optionally filtered by dataset."""
        tags = list(self._tags.values())
        if dataset:
            tags = [t for t in tags if t.dataset == dataset]
        return tags

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def vacuum(self) -> int:
        """Clean up old snapshots beyond retention period.

        Returns:
            Number of snapshots removed.
        """
        if self.lakehouse:
            return self.lakehouse.vacuum(
                older_than_days=self.config.max_history_days
            )
        return 0

    def get_timeline(
        self, dataset: str, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get the timeline of snapshots for a dataset.

        Args:
            dataset: Dataset name.
            start: Start of time range.
            end: End of time range.

        Returns:
            List of snapshot timeline entries.
        """
        if not self.lakehouse:
            return []

        snapshots = self.lakehouse.list_snapshots(dataset)

        if start:
            snapshots = [s for s in snapshots if s.timestamp >= start]
        if end:
            snapshots = [s for s in snapshots if s.timestamp <= end]

        return [
            {
                "snapshot_id": s.snapshot_id,
                "timestamp": s.timestamp.isoformat(),
                "file_count": len(s.files),
                "is_current": s.is_current,
            }
            for s in sorted(snapshots, key=lambda s: s.timestamp)
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get time travel statistics."""
        return {
            "enabled": self.config.enabled,
            "max_history_days": self.config.max_history_days,
            "total_branches": len(self._branches),
            "total_tags": len(self._tags),
            "active_branches": sum(1 for b in self._branches.values() if b.is_active),
        }
