"""
Walk-Forward Validator — Validates alpha via walk-forward testing.

Walk-forward validation:
    - Splits data into sequential train/test windows
    - Trains on past window, tests on next window
    - Rolls forward and aggregates results
    - More realistic than simple train/test split
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WFStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    MARGINAL = "marginal"
    NOT_TESTED = "not_tested"


@dataclass
class WalkForwardResult:
    individual_id: str
    status: WFStatus = WFStatus.NOT_TESTED
    n_windows: int = 0
    mean_ic: float = 0.0
    std_ic: float = 0.0
    ic_per_window: List[float] = field(default_factory=list)
    positive_window_ratio: float = 0.0
    overall_score: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)


class WalkForwardValidator:
    """
    Validates alpha via walk-forward testing.

    Walk-forward is the gold standard for preventing overfitting
    in time-series prediction problems.
    """

    def __init__(
        self,
        min_windows: int = 6,
        min_positive_window_ratio: float = 0.60,
        min_mean_ic: float = 0.01,
    ):
        self._min_windows = min_windows
        self._min_positive_ratio = min_positive_window_ratio
        self._min_mean_ic = min_mean_ic

    async def validate(
        self,
        individual_id: str,
        window_results: Optional[List[Dict[str, float]]] = None,
    ) -> WalkForwardResult:
        """
        Validate alpha via walk-forward testing.

        Args:
            individual_id: Candidate ID
            window_results: List of per-window metrics [{ic, sharpe, ...}, ...]
        """
        window_results = window_results or []
        result = WalkForwardResult(individual_id=individual_id)
        result.n_windows = len(window_results)

        if not window_results:
            result.status = WFStatus.NOT_TESTED
            return result

        # Extract IC per window
        ics = [w.get("ic", 0) for w in window_results]
        result.ic_per_window = ics
        result.mean_ic = sum(ics) / len(ics) if ics else 0

        # Std IC
        if len(ics) > 1:
            mean = result.mean_ic
            result.std_ic = (sum((x - mean) ** 2 for x in ics) / len(ics)) ** 0.5

        # Positive window ratio
        positive = sum(1 for ic in ics if ic > 0)
        result.positive_window_ratio = positive / max(len(ics), 1)

        # Checks
        if result.n_windows < self._min_windows:
            result.failure_reasons.append(
                f"Only {result.n_windows} windows, need {self._min_windows}"
            )

        if result.mean_ic < self._min_mean_ic:
            result.failure_reasons.append(
                f"Mean WF IC {result.mean_ic:.4f} < {self._min_mean_ic}"
            )

        if result.positive_window_ratio < self._min_positive_ratio:
            result.failure_reasons.append(
                f"Positive window ratio {result.positive_window_ratio:.2f} < {self._min_positive_ratio}"
            )

        # Overall score
        result.overall_score = (
            result.mean_ic * 10 * 0.35
            + result.positive_window_ratio * 0.35
            + (1.0 - min(result.std_ic, 1.0)) * 0.30
        )

        if result.overall_score >= 0.50 and not result.failure_reasons:
            result.status = WFStatus.PASSED
        elif result.failure_reasons:
            result.status = WFStatus.FAILED
        else:
            result.status = WFStatus.MARGINAL

        return result

    async def validate_batch(
        self,
        individuals: List[tuple[str, Optional[List[Dict[str, float]]]]],
    ) -> Dict[str, WalkForwardResult]:
        results = {}
        for oid, windows in individuals:
            results[oid] = await self.validate(oid, windows)
        return results
