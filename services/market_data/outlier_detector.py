"""
Outlier Detector — identifies anomalous market data values using
statistical methods (Z-score, IQR, MAD) with configurable thresholds.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OutlierMethod(str, Enum):
    Z_SCORE = "z_score"     # Z-score based (assumes normal dist)
    IQR = "iqr"             # Interquartile range
    MAD = "mad"             # Median absolute deviation
    PERCENTILE = "percentile"


@dataclass
class OutlierEvent:
    """A detected outlier."""

    instrument_id: str = ""
    field_name: str = ""
    value: float = 0.0
    expected_range: tuple[float, float] = (0.0, 0.0)
    method: OutlierMethod = OutlierMethod.Z_SCORE
    z_score: float = 0.0
    severity: str = "warning"
    timestamp_ns: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutlierConfig:
    """Configuration for outlier detection."""

    method: OutlierMethod = OutlierMethod.Z_SCORE
    z_score_threshold: float = 3.0           # Z-score > threshold = outlier
    iqr_multiplier: float = 1.5              # IQR * multiplier
    mad_threshold: float = 3.0               # MAD * threshold
    percentile_lower: float = 0.1            # 0.1%
    percentile_upper: float = 99.9           # 99.9%
    window_size: int = 1000                  # Rolling window for statistics
    min_samples: int = 30                    # Minimum samples before detecting
    alert_on_outlier: bool = True


class OutlierDetector:
    """
    Detects outlier values in market data streams.

    Supports multiple statistical methods:
    - Z-score (for approximately normal distributions)
    - IQR (Interquartile Range, robust to skew)
    - MAD (Median Absolute Deviation, robust to extreme outliers)
    - Percentile-based thresholds

    Maintains per-instrument, per-field rolling windows for
    adaptive threshold computation.
    """

    def __init__(self, config: Optional[OutlierConfig] = None) -> None:
        self._config = config or OutlierConfig()
        self._windows: dict[str, deque[float]] = {}    # "inst:field" → values
        self._outliers: list[OutlierEvent] = []
        self._stats: dict[str, int] = {"total_checked": 0, "total_outliers": 0}

    async def initialize(self) -> None:
        logger.info("OutlierDetector initialized (method: %s, threshold: %.1f)",
                     self._config.method.value, self._config.z_score_threshold)

    # ── Detection ──────────────────────────────────

    async def check(
        self,
        instrument_id: str,
        field_name: str,
        value: float,
        timestamp_ns: int = 0,
    ) -> Optional[OutlierEvent]:
        """
        Check if a value is an outlier.

        Returns OutlierEvent if outlier detected, None otherwise.
        """
        self._stats["total_checked"] += 1
        window_key = f"{instrument_id}:{field_name}"

        if window_key not in self._windows:
            self._windows[window_key] = deque(maxlen=self._config.window_size)

        window = self._windows[window_key]

        # Need minimum samples before detecting
        if len(window) < self._config.min_samples:
            window.append(value)
            return None

        if self._config.method == OutlierMethod.Z_SCORE:
            is_outlier, z_score, bounds = self._check_zscore(value, window)
        elif self._config.method == OutlierMethod.IQR:
            is_outlier, z_score, bounds = self._check_iqr(value, window)
        elif self._config.method == OutlierMethod.MAD:
            is_outlier, z_score, bounds = self._check_mad(value, window)
        elif self._config.method == OutlierMethod.PERCENTILE:
            is_outlier, z_score, bounds = self._check_percentile(value, window)
        else:
            is_outlier, z_score, bounds = False, 0.0, (0.0, 0.0)

        # Add value to window AFTER check (to avoid self-influence)
        window.append(value)

        if is_outlier:
            self._stats["total_outliers"] += 1
            outlier = OutlierEvent(
                instrument_id=instrument_id,
                field_name=field_name,
                value=value,
                expected_range=bounds,
                method=self._config.method,
                z_score=z_score,
                severity="warning" if abs(z_score) < 5.0 else "error",
                timestamp_ns=timestamp_ns or self._now_ns(),
            )
            self._outliers.append(outlier)

            if self._config.alert_on_outlier:
                logger.warning("Outlier: %s.%s = %.6f (z=%.2f, range=[%.6f, %.6f])",
                               instrument_id, field_name, value, z_score, *bounds)

            return outlier

        return None

    async def check_record(
        self, instrument_id: str, fields: dict[str, float], timestamp_ns: int = 0
    ) -> list[OutlierEvent]:
        """Check all numeric fields in a record for outliers."""
        outliers: list[OutlierEvent] = []
        for field_name, value in fields.items():
            result = await self.check(instrument_id, field_name, value, timestamp_ns)
            if result:
                outliers.append(result)
        return outliers

    async def check_batch(
        self, records: list[dict[str, Any]]
    ) -> list[OutlierEvent]:
        """Check a batch of records for outliers."""
        all_outliers: list[OutlierEvent] = []
        for record in records:
            inst_id = record.get("instrument_id", record.get("symbol", ""))
            ts = record.get("event_time", record.get("timestamp", 0))

            # Check common numeric fields
            numeric_fields = {}
            for field in ("price", "last", "bid", "ask", "volume", "turnover",
                         "open", "high", "low", "close", "quantity"):
                val = record.get(field)
                if isinstance(val, (int, float)):
                    numeric_fields[field] = float(val)

            outliers = await self.check_record(inst_id, numeric_fields, ts)
            all_outliers.extend(outliers)

        return all_outliers

    # ── Statistical methods ────────────────────────

    def _check_zscore(
        self, value: float, window: deque[float]
    ) -> tuple[bool, float, tuple[float, float]]:
        """Z-score based outlier detection."""
        n = len(window)
        mean = sum(window) / n
        variance = sum((x - mean) ** 2 for x in window) / n
        std = math.sqrt(variance) if variance > 0 else 1.0

        z_score = (value - mean) / std if std > 0 else 0.0
        threshold = self._config.z_score_threshold
        lower = mean - threshold * std
        upper = mean + threshold * std

        return abs(z_score) > threshold, z_score, (lower, upper)

    def _check_iqr(
        self, value: float, window: deque[float]
    ) -> tuple[bool, float, tuple[float, float]]:
        """IQR-based outlier detection."""
        sorted_vals = sorted(window)
        n = len(sorted_vals)
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = sorted_vals[q1_idx]
        q3 = sorted_vals[q3_idx]
        iqr = q3 - q1

        multiplier = self._config.iqr_multiplier
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        # Pseudo z-score
        median = sorted_vals[n // 2]
        z_score = (value - median) / (iqr / 1.35) if iqr > 0 else 0.0

        return value < lower or value > upper, z_score, (lower, upper)

    def _check_mad(
        self, value: float, window: deque[float]
    ) -> tuple[bool, float, tuple[float, float]]:
        """MAD-based outlier detection."""
        sorted_vals = sorted(window)
        n = len(sorted_vals)
        median = sorted_vals[n // 2]
        mad = sorted([abs(x - median) for x in sorted_vals])[n // 2]

        threshold = self._config.mad_threshold
        lower = median - threshold * mad
        upper = median + threshold * mad

        z_score = (value - median) / (mad / 0.6745) if mad > 0 else 0.0

        return value < lower or value > upper, z_score, (lower, upper)

    def _check_percentile(
        self, value: float, window: deque[float]
    ) -> tuple[bool, float, tuple[float, float]]:
        """Percentile-based outlier detection."""
        sorted_vals = sorted(window)
        n = len(sorted_vals)
        lower_idx = int(n * self._config.percentile_lower / 100)
        upper_idx = int(n * self._config.percentile_upper / 100)
        lower = sorted_vals[max(0, lower_idx)]
        upper = sorted_vals[min(n - 1, upper_idx)]

        return value < lower or value > upper, 0.0, (lower, upper)

    # ── Reporting ──────────────────────────────────

    async def get_recent_outliers(self, limit: int = 100) -> list[OutlierEvent]:
        """Get recent outlier events."""
        return self._outliers[-limit:]

    async def get_outliers_for_instrument(self, instrument_id: str) -> list[OutlierEvent]:
        """Get all outliers for a specific instrument."""
        return [o for o in self._outliers if o.instrument_id == instrument_id]

    async def reset(self) -> None:
        """Reset detection state."""
        self._windows.clear()
        self._outliers.clear()
        self._stats = {"total_checked": 0, "total_outliers": 0}

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @property
    def outlier_count(self) -> int:
        return len(self._outliers)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)


# Type alias for __init__.py compatibility
OutlierRecord = OutlierEvent
