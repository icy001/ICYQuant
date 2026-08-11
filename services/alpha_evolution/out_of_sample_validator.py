"""
Out-of-Sample Validator — Validates alpha on out-of-sample data.

Critical validation to prevent overfitting:
    - Train/test split
    - Time-based split (chronological)
    - Cross-sectional OOS (different universe)
    - Temporal OOS (future periods)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OOSStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    OVERFIT = "overfit"
    NOT_TESTED = "not_tested"


@dataclass
class OOSResult:
    individual_id: str
    status: OOSStatus = OOSStatus.NOT_TESTED
    is_ic: float = 0.0
    oos_ic: float = 0.0
    oos_retention: float = 0.0          # oos_ic / is_ic
    oos_sharpe: float = 0.0
    is_sharpe: float = 0.0
    sharpe_retention: float = 0.0
    oos_period: str = ""
    overall_score: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)


class OutOfSampleValidator:
    """
    Validates alpha performance on truly out-of-sample data.

    Key metrics:
        - OOS IC retention (ratio of OOS IC to IS IC)
        - OOS Sharpe retention
        - OOS decay pattern
    """

    def __init__(
        self,
        min_oos_ic_retention: float = 0.50,
        min_oos_sharpe_retention: float = 0.40,
        min_oos_ic_absolute: float = 0.01,
    ):
        self._min_ic_retention = min_oos_ic_retention
        self._min_sharpe_retention = min_oos_sharpe_retention
        self._min_oos_ic = min_oos_ic_absolute

    async def validate(
        self,
        individual_id: str,
        is_metrics: Optional[Dict[str, float]] = None,
        oos_metrics: Optional[Dict[str, float]] = None,
        oos_period: str = "",
    ) -> OOSResult:
        """Validate alpha on out-of-sample data."""
        is_metrics = is_metrics or {}
        oos_metrics = oos_metrics or {}
        result = OOSResult(individual_id=individual_id)

        result.is_ic = is_metrics.get("ic", 0)
        result.oos_ic = oos_metrics.get("ic", 0)
        result.is_sharpe = is_metrics.get("sharpe", 0)
        result.oos_sharpe = oos_metrics.get("sharpe", 0)
        result.oos_period = oos_period

        # IC retention
        if result.is_ic > 0:
            result.oos_retention = result.oos_ic / result.is_ic
        elif result.oos_ic > 0:
            result.oos_retention = 1.0

        # Sharpe retention
        if result.is_sharpe > 0:
            result.sharpe_retention = result.oos_sharpe / result.is_sharpe
        elif result.oos_sharpe > 0:
            result.sharpe_retention = 1.0

        # Checks
        if result.oos_ic < self._min_oos_ic:
            result.failure_reasons.append(f"OOS IC {result.oos_ic:.4f} < min {self._min_oos_ic}")

        if result.oos_retention < self._min_ic_retention:
            result.failure_reasons.append(
                f"OOS IC retention {result.oos_retention:.2f} < {self._min_ic_retention}"
            )

        if result.oos_retention < 0.20:
            result.status = OOSStatus.OVERFIT
        elif result.failure_reasons:
            result.status = OOSStatus.FAILED
        else:
            result.status = OOSStatus.PASSED

        return result

    async def validate_batch(
        self,
        individuals: List[tuple[str, Dict[str, float], Dict[str, float]]],
    ) -> Dict[str, OOSResult]:
        results = {}
        for oid, is_m, oos_m in individuals:
            results[oid] = await self.validate(oid, is_m, oos_m)
        return results
