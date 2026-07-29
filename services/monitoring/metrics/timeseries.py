"""Time Series Store.

In-memory time series database for storing and querying metrics.
Supports range queries, downsampling, and retention policies.

Usage::

    store = TimeSeriesStore(retention_seconds=86400)
    store.insert("cpu_pct", 45.2)
    store.insert("cpu_pct", 47.1)
    points = store.query("cpu_pct", start, end)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DataPoint:
    """A single timestamped metric value."""

    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "labels": self.labels,
        }


@dataclass
class TimeSeries:
    """A named time series with metadata."""

    name: str
    unit: str = ""
    description: str = ""
    points: List[DataPoint] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "description": self.description,
            "point_count": len(self.points),
            "first_timestamp": self.points[0].timestamp if self.points else None,
            "last_timestamp": self.points[-1].timestamp if self.points else None,
            "created_at": self.created_at,
        }


class TimeSeriesStore:
    """In-memory time series database.

    Stores named time series with configurable retention.
    Supports range queries and simple downsampling.
    """

    def __init__(self, retention_seconds: float = 86400.0 * 7) -> None:
        self._series: Dict[str, TimeSeries] = {}
        self._retention_seconds = retention_seconds
        self._insert_count: int = 0

    def create_series(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> TimeSeries:
        """Create a new time series."""
        if name in self._series:
            return self._series[name]
        ts = TimeSeries(name=name, unit=unit, description=description)
        self._series[name] = ts
        return ts

    def insert(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Insert a data point into a time series."""
        if name not in self._series:
            self.create_series(name)
        ts = self._series[name]
        ts.points.append(
            DataPoint(
                timestamp=timestamp if timestamp is not None else time.time(),
                value=value,
                labels=labels or {},
            )
        )
        self._insert_count += 1

    def query(
        self,
        name: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> List[DataPoint]:
        """Query data points for a time series within a time range."""
        ts = self._series.get(name)
        if not ts:
            return []

        if start is None and end is None:
            return list(ts.points)

        result = []
        for p in ts.points:
            if start is not None and p.timestamp < start:
                continue
            if end is not None and p.timestamp > end:
                continue
            result.append(p)
        return result

    def query_values(
        self,
        name: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> List[float]:
        """Query just the values (no metadata)."""
        return [p.value for p in self.query(name, start, end)]

    def latest(self, name: str) -> Optional[float]:
        """Get the most recent value for a time series."""
        ts = self._series.get(name)
        if not ts or not ts.points:
            return None
        return ts.points[-1].value

    def get_series(self, name: str) -> Optional[TimeSeries]:
        """Get a time series by name."""
        return self._series.get(name)

    def list_series(self) -> List[TimeSeries]:
        """List all time series."""
        return list(self._series.values())

    def downsample(
        self,
        name: str,
        interval_seconds: float,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> List[DataPoint]:
        """Downsample a time series to regular intervals using mean aggregation."""
        points = self.query(name, start, end)
        if not points:
            return []

        # Group by interval
        buckets: Dict[int, List[float]] = {}
        for p in points:
            bucket = int(p.timestamp / interval_seconds)
            buckets.setdefault(bucket, []).append(p.value)

        result = []
        for bucket in sorted(buckets):
            vals = buckets[bucket]
            avg = sum(vals) / len(vals)
            result.append(DataPoint(
                timestamp=bucket * interval_seconds,
                value=avg,
            ))
        return result

    def cleanup(self) -> int:
        """Remove data points older than retention period. Returns count removed."""
        cutoff = time.time() - self._retention_seconds
        removed = 0
        for ts in self._series.values():
            old_len = len(ts.points)
            ts.points = [p for p in ts.points if p.timestamp >= cutoff]
            removed += old_len - len(ts.points)
        return removed

    @property
    def point_count(self) -> int:
        """Total number of data points across all series."""
        return sum(len(ts.points) for ts in self._series.values())

    @property
    def series_count(self) -> int:
        """Number of time series."""
        return len(self._series)
