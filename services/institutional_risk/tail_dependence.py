"""TailDependence — measure tail dependence between assets/strategies.

Normal correlation and tail correlation can be very different:
- Normal: corr(A,B) = 0.15
- Tail: corr(A,B) = 0.85

This matters because diversification fails precisely when you need it most.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TailDependenceResult:
    """Tail dependence analysis result."""

    pair: Tuple[str, str] = ("", "")
    normal_correlation: float = 0.0
    lower_tail_dependence: float = 0.0
    upper_tail_dependence: float = 0.0
    tail_asymmetry: float = 0.0  # lower - upper
    tail_correlation_increase: float = 0.0
    risk_multiplication: float = 1.0
    warning: str = ""


@dataclass
class TailDependenceReport:
    """Aggregate tail dependence report."""

    entity_id: str
    pairs: Dict[Tuple[str, str], TailDependenceResult] = field(default_factory=dict)
    average_lower_tail: float = 0.0
    max_lower_tail: float = 0.0
    max_lower_tail_pair: Tuple[str, str] = ("", "")
    systemic_tail_risk: float = 0.0
    high_tail_pairs: List[Tuple[str, str]] = field(default_factory=list)


class TailDependenceEstimator:
    """Estimates tail dependence between pairs of return series.

    Usage::

        estimator = TailDependenceEstimator()
        result = estimator.estimate_pair(returns_a, returns_b, ("A", "B"))
        print(f"Tail dependence: {result.lower_tail_dependence:.2f}")
    """

    def __init__(
        self,
        tail_quantile: float = 0.10,
        high_tail_threshold: float = 0.70,
    ):
        self._tail_quantile = tail_quantile
        self._high_tail_threshold = high_tail_threshold

    def estimate_pair(
        self,
        returns_a: List[float],
        returns_b: List[float],
        pair: Tuple[str, str],
    ) -> TailDependenceResult:
        """Estimate tail dependence for a pair.

        Uses empirical tail dependence coefficient:
            λ = P(Y in tail | X in tail)
        """
        n = min(len(returns_a), len(returns_b))
        if n < 50:
            return TailDependenceResult(pair=pair)

        x = returns_a[:n]
        y = returns_b[:n]

        # normal correlation
        mx = sum(x) / n
        my = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (n - 1)
        vx = sum((xi - mx) ** 2 for xi in x) / (n - 1)
        vy = sum((yi - my) ** 2 for yi in y) / (n - 1)
        normal_corr = 0.0
        if vx > 0 and vy > 0:
            normal_corr = max(-1.0, min(1.0, cov / math.sqrt(vx * vy)))

        # tail quantile thresholds
        threshold = int(n * self._tail_quantile)

        # lower tail (both in bottom tail)
        lower_x = sorted(range(n), key=lambda i: x[i])[:threshold]
        lower_y = sorted(range(n), key=lambda i: y[i])[:threshold]
        both_lower = len(set(lower_x) & set(lower_y))
        lower_tail = both_lower / max(threshold, 1)

        # upper tail (both in top tail)
        upper_x = sorted(range(n), key=lambda i: x[i], reverse=True)[:threshold]
        upper_y = sorted(range(n), key=lambda i: y[i], reverse=True)[:threshold]
        both_upper = len(set(upper_x) & set(upper_y))
        upper_tail = both_upper / max(threshold, 1)

        # asymmetry
        asymmetry = lower_tail - upper_tail

        # how much does tail correlation exceed normal correlation
        tail_increase = lower_tail - normal_corr

        # risk multiplication: if you thought diversification was based on normal corr
        risk_mult = 1.0
        if normal_corr < 1.0:
            risk_mult = math.sqrt((1 + lower_tail) / max(1 + normal_corr, 1e-9))

        # warning
        warning = ""
        if lower_tail > self._high_tail_threshold:
            warning = (
                f"HIGH TAIL DEPENDENCE: {pair[0]}-{pair[1]} = {lower_tail:.2f} "
                f"(normal: {normal_corr:.2f})"
            )

        return TailDependenceResult(
            pair=pair,
            normal_correlation=normal_corr,
            lower_tail_dependence=lower_tail,
            upper_tail_dependence=upper_tail,
            tail_asymmetry=asymmetry,
            tail_correlation_increase=tail_increase,
            risk_multiplication=risk_mult,
            warning=warning,
        )

    def estimate_all(
        self,
        entity_id: str,
        returns_dict: Dict[str, List[float]],
    ) -> TailDependenceReport:
        """Estimate tail dependence for all pairs in a return dict.

        Args:
            entity_id: portfolio id
            returns_dict: {strategy_id: [returns]}
        """
        keys = sorted(returns_dict.keys())
        n = len(keys)

        report = TailDependenceReport(entity_id=entity_id)

        max_lower = 0.0
        max_pair = ("", "")

        for i in range(n):
            for j in range(i + 1, n):
                pair = (keys[i], keys[j])
                result = self.estimate_pair(
                    returns_dict[keys[i]],
                    returns_dict[keys[j]],
                    pair,
                )
                report.pairs[pair] = result

                if result.lower_tail_dependence > max_lower:
                    max_lower = result.lower_tail_dependence
                    max_pair = pair

                if result.lower_tail_dependence > self._high_tail_threshold:
                    report.high_tail_pairs.append(pair)

        # aggregate
        if report.pairs:
            report.average_lower_tail = (
                sum(p.lower_tail_dependence for p in report.pairs.values())
                / len(report.pairs)
            )
        report.max_lower_tail = max_lower
        report.max_lower_tail_pair = max_pair
        report.systemic_tail_risk = len(report.high_tail_pairs) / max(len(report.pairs), 1)

        return report
