"""CorrelationSpike — detect sudden correlation increases.

Monitors pairwise correlations for abrupt spikes that signal
the start of a correlation regime change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SpikeEvent:
    """A detected correlation spike."""

    pair: Tuple[str, str] = ("", "")
    correlation_before: float = 0.0
    correlation_after: float = 0.0
    spike_magnitude: float = 0.0
    z_score: float = 0.0
    timestamp: float = 0.0


@dataclass
class SpikeResult:
    """Correlation spike detection result."""

    entity_id: str
    spikes_detected: int = 0
    spike_events: List[SpikeEvent] = field(default_factory=list)
    max_spike_magnitude: float = 0.0
    max_spike_pair: Tuple[str, str] = ("", "")
    affected_count: int = 0
    risk_score: float = 0.0


class CorrelationSpikeDetector:
    """Detects sudden correlation spikes.

    A correlation spike occurs when a pairwise correlation
    increases rapidly above its historical average, signaling
    changing market dynamics.

    Usage::

        detector = CorrelationSpikeDetector(spike_threshold=0.20)
        result = detector.detect(
            "portfolio_1",
            current_pairs={"A,B": 0.65},
            historical_pairs={"A,B": (0.25, 0.10)},
        )
    """

    def __init__(
        self,
        spike_threshold: float = 0.20,
        z_score_threshold: float = 2.0,
    ):
        self._spike_threshold = spike_threshold
        self._z_threshold = z_score_threshold

    def detect(
        self,
        entity_id: str,
        current_pairs: Dict[Tuple[str, str], float],
        historical_stats: Dict[Tuple[str, str], Tuple[float, float]],
        timestamp: Optional[float] = None,
    ) -> SpikeResult:
        """Detect correlation spikes.

        Args:
            entity_id: portfolio id
            current_pairs: {(entity_a, entity_b): current_correlation}
            historical_stats: {(entity_a, entity_b): (avg, std)}
            timestamp: detection timestamp
        """
        import time

        result = SpikeResult(entity_id=entity_id)

        for pair, current_corr in current_pairs.items():
            hist = historical_stats.get(pair)
            if hist is None:
                # try reversed
                hist = historical_stats.get((pair[1], pair[0]))

            if hist is None:
                continue

            avg_corr, std_corr = hist

            # absolute spike
            abs_spike = current_corr - avg_corr

            # z-score
            z_score = 0.0
            if std_corr > 0:
                z_score = abs_spike / std_corr

            if abs_spike > self._spike_threshold or z_score > self._z_threshold:
                event = SpikeEvent(
                    pair=pair,
                    correlation_before=avg_corr,
                    correlation_after=current_corr,
                    spike_magnitude=abs_spike,
                    z_score=z_score,
                    timestamp=timestamp or time.time(),
                )
                result.spike_events.append(event)
                result.spikes_detected += 1

                if abs_spike > result.max_spike_magnitude:
                    result.max_spike_magnitude = abs_spike
                    result.max_spike_pair = pair

        result.affected_count = len(set(
            p for event in result.spike_events
            for p in event.pair
        ))

        # risk score: weighted by spike count and magnitude
        result.risk_score = min(100.0, result.spikes_detected * 10 + result.max_spike_magnitude * 100)

        return result

    def detect_from_returns(
        self,
        entity_id: str,
        current_returns: Dict[str, List[float]],
        historical_returns: Dict[str, List[float]],
        spike_threshold: Optional[float] = None,
    ) -> SpikeResult:
        """Detect spikes directly from return series.

        Compares current correlation to historical correlation
        computed from longer return history.

        Args:
            entity_id: portfolio id
            current_returns: recent (short) return series
            historical_returns: longer historical return series
            spike_threshold: override threshold
        """
        threshold = spike_threshold or self._spike_threshold

        keys = sorted(set(current_returns.keys()) & set(historical_returns.keys()))
        n = len(keys)

        current_pairs: dict = {}
        historical_stats: dict = {}

        for i in range(n):
            for j in range(i + 1, n):
                pair = (keys[i], keys[j])

                # current correlation (short window)
                c1 = current_returns[keys[i]]
                c2 = current_returns[keys[j]]
                ml = min(len(c1), len(c2))
                if ml >= 5:
                    curr_corr = self._corr(c1[-ml:], c2[-ml:])
                    current_pairs[pair] = curr_corr

                # historical stats (long window)
                h1 = historical_returns[keys[i]]
                h2 = historical_returns[keys[j]]
                hl = min(len(h1), len(h2))
                if hl >= 30:
                    # rolling correlation stats
                    window = 20
                    rolling_corrs = []
                    for k in range(window, hl):
                        w1 = h1[k - window:k]
                        w2 = h2[k - window:k]
                        rolling_corrs.append(self._corr(w1, w2))
                    if rolling_corrs:
                        avg = sum(rolling_corrs) / len(rolling_corrs)
                        var = sum((r - avg) ** 2 for r in rolling_corrs) / len(rolling_corrs)
                        historical_stats[pair] = (avg, math.sqrt(max(var, 0.0)))

        return self.detect(entity_id, current_pairs, historical_stats)

    @staticmethod
    def _corr(x: List[float], y: List[float]) -> float:
        """Compute Pearson correlation."""
        n = len(x)
        if n < 2:
            return 0.0
        mx = sum(x) / n
        my = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (n - 1)
        vx = sum((xi - mx) ** 2 for xi in x) / (n - 1)
        vy = sum((yi - my) ** 2 for yi in y) / (n - 1)
        if vx > 0 and vy > 0:
            return max(-1.0, min(1.0, cov / math.sqrt(vx * vy)))
        return 0.0
