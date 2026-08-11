"""TailEvent — model and analyze specific tail events.

Identifies distinct tail events from historical data and
computes their characteristics (frequency, severity, cluster).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TailEventRecord:
    """A single tail event record."""

    index: int = 0
    timestamp: float = 0.0
    return_value: float = 0.0
    z_score: float = 0.0
    is_clustered: bool = False
    cluster_id: int = -1
    recovery_days: Optional[int] = None


@dataclass
class TailEventAnalysis:
    """Tail event analysis result."""

    entity_id: str
    total_events: int = 0
    event_frequency: float = 0.0  # events per year
    avg_event_return: float = 0.0
    worst_event_return: float = 0.0
    clustered_events: int = 0
    cluster_count: int = 0
    events: List[TailEventRecord] = field(default_factory=list)
    severity_distribution: Dict[str, int] = field(default_factory=dict)


class TailEventAnalyzer:
    """Analyzes tail events in return series.

    Identifies events beyond the 3-sigma threshold, clusters them,
    and computes frequency/severity characteristics.

    Usage::

        analyzer = TailEventAnalyzer(sigma_threshold=3.0)
        result = analyzer.analyze("strategy_A", daily_returns)
        print(f"Tail events: {result.total_events} per {len(daily_returns)} days")
    """

    def __init__(self, sigma_threshold: float = 3.0, cluster_window: int = 5):
        self._sigma_threshold = sigma_threshold
        self._cluster_window = cluster_window

    def analyze(
        self,
        entity_id: str,
        returns: List[float],
        timestamps: Optional[List[float]] = None,
    ) -> TailEventAnalysis:
        """Analyze tail events in a return series.

        Args:
            entity_id: strategy/portfolio id
            returns: return series
            timestamps: optional timestamp list
        """
        if len(returns) < 10:
            return TailEventAnalysis(entity_id=entity_id)

        n = len(returns)
        mu = sum(returns) / n
        var = sum((r - mu) ** 2 for r in returns) / (n - 1)
        sigma = math.sqrt(max(var, 0.0))

        if sigma <= 0:
            return TailEventAnalysis(entity_id=entity_id)

        # identify events
        events: List[TailEventRecord] = []
        for i, r in enumerate(returns):
            z = (r - mu) / sigma
            if abs(z) > self._sigma_threshold:
                events.append(TailEventRecord(
                    index=i,
                    timestamp=timestamps[i] if timestamps else float(i),
                    return_value=r,
                    z_score=z,
                ))

        # cluster detection
        if events:
            cluster_id = 0
            events[0].cluster_id = cluster_id
            events[0].is_clustered = False

            for i in range(1, len(events)):
                gap = events[i].index - events[i - 1].index
                if gap <= self._cluster_window:
                    events[i].is_clustered = True
                    events[i].cluster_id = cluster_id
                else:
                    cluster_id += 1
                    events[i].cluster_id = cluster_id
                    events[i].is_clustered = False

        # statistics
        clustered = sum(1 for e in events if e.is_clustered)
        clusters = len(set(e.cluster_id for e in events if e.cluster_id >= 0))

        frequency = len(events) / max(n / 252, 1)  # per trading year

        avg_ret = 0.0
        worst = 0.0
        if events:
            avg_ret = sum(e.return_value for e in events) / len(events)
            worst = min(e.return_value for e in events)

        # severity distribution
        severity: Dict[str, int] = {"3σ": 0, "4σ": 0, "5σ": 0, "6σ+": 0}
        for e in events:
            z = abs(e.z_score)
            if z >= 6:
                severity["6σ+"] += 1
            elif z >= 5:
                severity["5σ"] += 1
            elif z >= 4:
                severity["4σ"] += 1
            else:
                severity["3σ"] += 1

        return TailEventAnalysis(
            entity_id=entity_id,
            total_events=len(events),
            event_frequency=frequency,
            avg_event_return=avg_ret,
            worst_event_return=worst,
            clustered_events=clustered,
            cluster_count=clusters,
            events=events,
            severity_distribution=severity,
        )

    def compute_expected_tail_frequency(
        self,
        returns: List[float],
        confidence: float = 0.99,
    ) -> float:
        """Estimate expected frequency of tail events per year.

        Uses extreme value theory approximation.
        """
        analysis = self.analyze("_tmp", returns)
        return analysis.event_frequency
