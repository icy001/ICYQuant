"""
Transaction Cost Analyzer — Estimates real-world trading costs for alphas.

Cost components:
    - Commission (broker fees)
    - Spread (bid-ask)
    - Slippage (execution delay)
    - Market impact (price movement from order)
    - Turnover cost

Converts "gross alpha" to "net alpha" by subtracting realistic costs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TransactionCostResult:
    individual_id: str
    commission_bps: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0
    total_cost_bps: float = 0.0
    gross_sharpe: float = 0.0
    net_sharpe: float = 0.0
    sharpe_retention: float = 0.0
    annual_cost_pct: float = 0.0
    overall_score: float = 0.0
    warnings: List[str] = field(default_factory=list)


class TransactionCostAnalyzer:
    """
    Estimates total transaction costs for alpha strategies.

    The evolution should optimize for NET performance, not gross.
    """

    def __init__(
        self,
        commission_bps: float = 1.0,
        spread_bps: float = 2.0,
        slippage_bps: float = 1.0,
        max_total_cost_bps: float = 15.0,
        min_sharpe_retention: float = 0.50,
    ):
        self._commission = commission_bps
        self._spread = spread_bps
        self._slippage = slippage_bps
        self._max_total_cost = max_total_cost_bps
        self._min_sharpe_retention = min_sharpe_retention

    async def analyze(
        self,
        individual_id: str,
        metrics: Optional[Dict[str, float]] = None,
    ) -> TransactionCostResult:
        """Estimate transaction costs for an alpha."""
        metrics = metrics or {}
        result = TransactionCostResult(individual_id=individual_id)

        result.commission_bps = self._commission
        result.spread_bps = self._spread
        result.slippage_bps = self._slippage
        result.market_impact_bps = metrics.get("market_impact_bps", 2.0)
        result.gross_sharpe = metrics.get("gross_sharpe", 0)
        result.net_sharpe = metrics.get("net_sharpe", 0)

        result.total_cost_bps = (
            result.commission_bps
            + result.spread_bps
            + result.slippage_bps
            + result.market_impact_bps
        )

        # Annual cost estimate
        turnover = metrics.get("annual_turnover", 12)
        result.annual_cost_pct = result.total_cost_bps * turnover / 10000

        # Sharpe retention
        if result.gross_sharpe > 0:
            result.sharpe_retention = result.net_sharpe / result.gross_sharpe
        elif result.net_sharpe > 0:
            result.sharpe_retention = 1.0

        if result.total_cost_bps > self._max_total_cost:
            result.warnings.append(
                f"Total cost {result.total_cost_bps:.0f}bps > max {self._max_total_cost}bps"
            )

        if result.gross_sharpe > 0 and result.sharpe_retention < self._min_sharpe_retention:
            result.warnings.append(
                f"Sharpe retention {result.sharpe_retention:.2f} < {self._min_sharpe_retention}"
            )

        result.overall_score = max(0, result.sharpe_retention)

        return result

    async def analyze_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[str, float]]]],
    ) -> Dict[str, TransactionCostResult]:
        results = {}
        for oid, metrics in individuals:
            results[oid] = await self.analyze(oid, metrics)
        return results

    @property
    def commission_bps(self) -> float:
        return self._commission
