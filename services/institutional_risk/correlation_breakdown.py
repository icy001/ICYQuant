"""CorrelationBreakdown — detect when diversification suddenly fails.

In crisis periods, correlations tend to converge to 1.0,
rendering diversification useless. This module detects and
quantifies this phenomenon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BreakdownEvent:
    """A correlation breakdown event."""

    timestamp: float = 0.0
    entity_id: str = ""
    avg_corr_before: float = 0.0
    avg_corr_after: float = 0.0
    corr_increase_pct: float = 0.0
    pairs_affected: int = 0
    severity: str = "MODERATE"  # MODERATE, SEVERE, EXTREME
    diversification_loss_pct: float = 0.0


@dataclass
class BreakdownResult:
    """Correlation breakdown analysis result."""

    entity_id: str
    breakdown_detected: bool = False
    current_avg_corr: float = 0.0
    baseline_avg_corr: float = 0.0
    corr_increase: float = 0.0
    diversification_erosion: float = 0.0
    implied_risk_multiplier: float = 1.0
    event: Optional[BreakdownEvent] = None


class CorrelationBreakdownDetector:
    """Detects correlation breakdown (diversification failure).

    In normal times: corr(A,B) ≈ 0.2
    In crisis: corr(A,B) → 0.8

    This module tracks the "correlation regime" and detects
    transitions to dangerous high-correlation states.

    Usage::

        detector = CorrelationBreakdownDetector()
        result = detector.detect("portfolio_1", current_returns, historical_returns)
        if result.breakdown_detected:
            print(f"CRISIS: correlations up {result.corr_increase:.2f}")
    """

    def __init__(
        self,
        breakdown_threshold: float = 0.30,
        severe_threshold: float = 0.50,
        extreme_threshold: float = 0.70,
    ):
        self._breakdown_threshold = breakdown_threshold
        self._severe_threshold = severe_threshold
        self._extreme_threshold = extreme_threshold
        self._history: List[BreakdownEvent] = []

    def detect(
        self,
        entity_id: str,
        current_returns: Dict[str, List[float]],
        baseline_avg_corr: float,
        baseline_pair_count: int = 0,
        timestamp: Optional[float] = None,
    ) -> BreakdownResult:
        """Detect if correlation breakdown has occurred.

        Args:
            entity_id: portfolio or strategy pool id
            current_returns: current return series
            baseline_avg_corr: historical average correlation
            baseline_pair_count: number of pairs in baseline
            timestamp: detection timestamp
        """
        import time

        # compute current average correlation
        keys = list(current_returns.keys())
        n = len(keys)
        if n < 2:
            return BreakdownResult(entity_id=entity_id, baseline_avg_corr=baseline_avg_corr)

        correlations = []
        pairs_used = 0
        for i in range(n):
            for j in range(i + 1, n):
                s1 = current_returns[keys[i]]
                s2 = current_returns[keys[j]]
                min_len = min(len(s1), len(s2))
                if min_len < 5:
                    continue
                s1 = s1[-min_len:]
                s2 = s2[-min_len:]
                mu1 = sum(s1) / min_len
                mu2 = sum(s2) / min_len
                cov = sum((x - mu1) * (y - mu2) for x, y in zip(s1, s2)) / (min_len - 1)
                var1 = sum((x - mu1) ** 2 for x in s1) / (min_len - 1)
                var2 = sum((y - mu2) ** 2 for y in s2) / (min_len - 1)
                if var1 > 0 and var2 > 0:
                    c = cov / (math.sqrt(var1) * math.sqrt(var2))
                    correlations.append(max(-1.0, min(1.0, c)))
                    pairs_used += 1

        if not correlations:
            return BreakdownResult(entity_id=entity_id, baseline_avg_corr=baseline_avg_corr)

        current_avg_corr = sum(correlations) / len(correlations)
        corr_increase = current_avg_corr - baseline_avg_corr

        # breakdown detection
        breakdown = corr_increase > self._breakdown_threshold

        # severity
        severity = "NONE"
        if break_down:
            if corr_increase > self._extreme_threshold:
                severity = "EXTREME"
            elif corr_increase > self._severe_threshold:
                severity = "SEVERE"
            else:
                severity = "MODERATE"

        # diversification erosion: how much diversification is lost
        # original portfolio risk reduction: sqrt(1 + (n-1)*corr) / sqrt(n)
        div_erosion = 0.0
        if n > 1:
            original_div = math.sqrt(1 + (n - 1) * baseline_avg_corr) / math.sqrt(n)
            current_div = math.sqrt(1 + (n - 1) * current_avg_corr) / math.sqrt(n)
            if original_div > 0:
                div_erosion = (current_div - original_div) / original_div * 100

        # implied risk multiplier
        risk_multiplier = 1.0
        if baseline_avg_corr < 1.0:
            risk_multiplier = math.sqrt(
                (1 + (n - 1) * current_avg_corr) / max(1 + (n - 1) * baseline_avg_corr, 1e-9)
            )

        result = BreakdownResult(
            entity_id=entity_id,
            breakdown_detected=breakdown,
            current_avg_corr=current_avg_corr,
            baseline_avg_corr=baseline_avg_corr,
            corr_increase=corr_increase,
            diversification_erosion=div_erosion,
            implied_risk_multiplier=risk_multiplier,
        )

        if breakdown:
            event = BreakdownEvent(
                timestamp=timestamp or time.time(),
                entity_id=entity_id,
                avg_corr_before=baseline_avg_corr,
                avg_corr_after=current_avg_corr,
                corr_increase_pct=corr_increase * 100,
                pairs_affected=pairs_used,
                severity=severity,
                diversification_loss_pct=div_erosion,
            )
            result.event = event
            self._history.append(event)

        return result

    def get_history(self) -> List[BreakdownEvent]:
        """Get all detected breakdown events."""
        return list(self._history)

    def reset(self) -> None:
        """Reset breakdown history."""
        self._history.clear()
