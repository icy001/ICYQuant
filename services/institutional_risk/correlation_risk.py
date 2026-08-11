"""CorrelationRisk — correlation risk monitoring and detection.

Monitors pairwise correlations, detects abnormal changes,
and warns when diversification is breaking down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CorrelationReport:
    """Correlation risk report."""

    entity_id: str
    average_correlation: float = 0.0
    max_correlation: float = 0.0
    max_correlation_pair: Tuple[str, str] = ("", "")
    min_correlation: float = 0.0
    correlation_std: float = 0.0
    diversification_ratio: float = 1.0
    pairs: Dict[Tuple[str, str], float] = field(default_factory=dict)
    risk_level: str = "LOW"  # LOW, MODERATE, HIGH, EXTREME
    warnings: List[str] = field(default_factory=list)


class CorrelationRiskMonitor:
    """Monitors correlation risk across strategies/portfolios.

    Detects dangerous correlation regimes:
    - High average correlation (diversification failure)
    - Correlation spikes (sudden increases)
    - Correlation breakdown (regime change)

    Usage::

        monitor = CorrelationRiskMonitor()
        report = monitor.analyze("portfolio_1", returns_dict)
        if report.risk_level == "EXTREME":
            print("WARNING: Diversification has collapsed")
    """

    def __init__(
        self,
        high_corr_threshold: float = 0.60,
        extreme_corr_threshold: float = 0.80,
        avg_corr_warning: float = 0.40,
        avg_corr_extreme: float = 0.60,
    ):
        self._high_threshold = high_corr_threshold
        self._extreme_threshold = extreme_corr_threshold
        self._avg_warning = avg_corr_warning
        self._avg_extreme = avg_corr_extreme

    def analyze(
        self,
        entity_id: str,
        returns_dict: Dict[str, List[float]],
        labels: Optional[List[str]] = None,
    ) -> CorrelationReport:
        """Analyze correlation structure.

        Args:
            entity_id: portfolio or capital pool id
            returns_dict: {strategy_id: [returns]}
            labels: optional entity labels
        """
        keys = sorted(returns_dict.keys())
        n = len(keys)

        if n < 2:
            return CorrelationReport(entity_id=entity_id)

        # compute all pairwise correlations
        pairs: Dict[Tuple[str, str], float] = {}
        correlations: List[float] = []

        max_corr = -1.0
        max_pair = ("", "")
        min_corr = 2.0

        for i in range(n):
            for j in range(i + 1, n):
                s1 = returns_dict[keys[i]]
                s2 = returns_dict[keys[j]]
                min_len = min(len(s1), len(s2))

                if min_len < 5:
                    continue

                s1 = s1[:min_len]
                s2 = s2[:min_len]

                mu1 = sum(s1) / min_len
                mu2 = sum(s2) / min_len

                cov = sum((x - mu1) * (y - mu2) for x, y in zip(s1, s2)) / (min_len - 1)
                var1 = sum((x - mu1) ** 2 for x in s1) / (min_len - 1)
                var2 = sum((y - mu2) ** 2 for y in s2) / (min_len - 1)

                corr_coef = 0.0
                if var1 > 0 and var2 > 0:
                    corr_coef = cov / (math.sqrt(var1) * math.sqrt(var2))
                    corr_coef = max(-1.0, min(1.0, corr_coef))

                pair = (keys[i], keys[j])
                pairs[pair] = corr_coef
                correlations.append(corr_coef)

                if corr_coef > max_corr:
                    max_corr = corr_coef
                    max_pair = pair
                if corr_coef < min_corr:
                    min_corr = corr_coef

        if not correlations:
            return CorrelationReport(entity_id=entity_id)

        avg_corr = sum(correlations) / len(correlations)
        corr_std = (
            (sum((c - avg_corr) ** 2 for c in correlations) / (len(correlations) - 1)) ** 0.5
            if len(correlations) > 1 else 0.0
        )

        # diversification ratio
        div_ratio = 1.0 / max(avg_corr, 1e-9) if avg_corr > 0 else 10.0

        # risk level
        risk_level = "LOW"
        warnings = []

        if max_corr > self._extreme_threshold:
            risk_level = "EXTREME"
            warnings.append(f"Extreme pairwise correlation: {max_pair} = {max_corr:.2f}")
        elif max_corr > self._high_threshold:
            risk_level = "HIGH"
            warnings.append(f"High pairwise correlation: {max_pair} = {max_corr:.2f}")

        if avg_corr > self._avg_extreme:
            risk_level = "EXTREME"
            warnings.append(f"Extreme average correlation: {avg_corr:.2f}")
        elif avg_corr > self._avg_warning:
            if risk_level == "LOW":
                risk_level = "MODERATE"
            warnings.append(f"Elevated average correlation: {avg_corr:.2f}")

        return CorrelationReport(
            entity_id=entity_id,
            average_correlation=avg_corr,
            max_correlation=max_corr,
            max_correlation_pair=max_pair,
            min_correlation=min_corr,
            correlation_std=corr_std,
            diversification_ratio=div_ratio,
            pairs=pairs,
            risk_level=risk_level,
            warnings=warnings,
        )

    def compute_correlation_surprise(
        self,
        current_corr: float,
        historical_avg_corr: float,
        historical_std_corr: float,
    ) -> float:
        """Compute correlation surprise z-score.

        How many standard deviations from historical average?
        """
        if historical_std_corr <= 0:
            return 0.0
        return (current_corr - historical_avg_corr) / historical_std_corr
