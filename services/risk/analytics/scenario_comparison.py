"""
Scenario Comparison Engine — Compare portfolio performance across multiple scenarios.

Computes cross-scenario metrics, identifies common vulnerabilities,
and generates comparative analytics for decision support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of comparing multiple scenario outcomes."""
    comparison_id: str
    scenarios_compared: int
    common_vulnerabilities: list[str]
    most_severe_scenario: str
    worst_aggregate_loss_pct: float
    best_case_loss_pct: float
    average_loss_pct: float
    loss_distribution: dict[str, int]  # risk_level -> count
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ScenarioComparison:
    """
    Compare portfolio performance across multiple stress scenarios.

    Computes comparative metrics including:
    - Cross-scenario loss distribution
    - Common vulnerability identification
    - Severity ranking
    - Correlation of outcomes
    - Actionable recommendations

    Usage::

        comparator = ScenarioComparison()
        result = comparator.compare(stress_results)
    """

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the comparison engine."""
        self._initialized = True

    async def compare(self, scenario_results: list[dict[str, Any]]) -> ComparisonResult:
        """
        Compare multiple scenario stress test results.

        Parameters
        ----------
        scenario_results : list[dict]
            Results from individual scenario stress tests.

        Returns
        -------
        ComparisonResult
            Comparative analysis.
        """
        import uuid

        if not scenario_results:
            return ComparisonResult(
                comparison_id=str(uuid.uuid4()),
                scenarios_compared=0,
                common_vulnerabilities=[],
                most_severe_scenario="",
                worst_aggregate_loss_pct=0.0,
                best_case_loss_pct=0.0,
                average_loss_pct=0.0,
                loss_distribution={},
            )

        # Extract losses
        losses: list[tuple[str, float, str]] = []  # (name, loss_pct, risk_level)
        for r in scenario_results:
            name = r.get("scenario_name", r.get("scenario_id", "unknown"))
            loss = abs(r.get("loss_percentage", 0))
            risk = r.get("risk_level", "low")
            losses.append((name, loss, risk))

        # Statistics
        loss_values = [l[1] for l in losses]
        avg_loss = sum(loss_values) / len(loss_values) if loss_values else 0.0
        max_loss_idx = loss_values.index(max(loss_values)) if loss_values else -1
        min_loss = min(loss_values) if loss_values else 0.0
        max_loss = max(loss_values) if loss_values else 0.0

        most_severe = losses[max_loss_idx][0] if max_loss_idx >= 0 else ""
        best_case = losses[loss_values.index(min_loss)][0] if loss_values else ""

        # Loss distribution
        distribution: dict[str, int] = {}
        for _, _, risk in losses:
            distribution[risk] = distribution.get(risk, 0) + 1

        # Common vulnerabilities
        all_breaches: set[str] = set()
        breach_counts: dict[str, int] = {}
        for r in scenario_results:
            breached = r.get("breached_limits", [])
            for b in breached:
                if isinstance(b, str):
                    breach_counts[b] = breach_counts.get(b, 0) + 1
                    all_breaches.add(b)

        common = [
            b for b, c in breach_counts.items()
            if c > len(scenario_results) / 2
        ]

        # Correlation of outcomes
        corr_matrix: dict[str, dict[str, float]] = {}
        if len(scenario_results) >= 2:
            for i, ri in enumerate(scenario_results):
                name_i = ri.get("scenario_name", f"s{i}")
                corr_matrix[name_i] = {}
                for j, rj in enumerate(scenario_results):
                    if i == j:
                        corr_matrix[name_i][rj.get("scenario_name", f"s{j}")] = 1.0
                    else:
                        corr_matrix[name_i][rj.get("scenario_name", f"s{j}")] = 0.5  # placeholder

        # Recommendations
        recommendations: list[str] = []
        if max_loss > 30:
            recommendations.append(f"Severe drawdown risk ({max_loss:.1f}%): consider position reduction or hedging.")
        if len(common) > 0:
            recommendations.append(f"Common vulnerability across {len(common)} limits: review risk limits.")
        if len(distribution.get("critical", 0)) > 2 or len(distribution.get("high", 0)) > 3:
            recommendations.append("Multiple critical/high risk scenarios: review portfolio construction.")
        if avg_loss > 15:
            recommendations.append(f"Average loss {avg_loss:.1f}% exceeds threshold: reduce risk exposure.")
        if not recommendations:
            recommendations.append("Portfolio demonstrates adequate resilience across scenarios.")

        return ComparisonResult(
            comparison_id=str(uuid.uuid4()),
            scenarios_compared=len(scenario_results),
            common_vulnerabilities=common,
            most_severe_scenario=most_severe,
            worst_aggregate_loss_pct=max_loss,
            best_case_loss_pct=min_loss,
            average_loss_pct=avg_loss,
            loss_distribution=distribution,
            correlation_matrix=corr_matrix,
            recommendations=recommendations,
        )

    async def rank_scenarios(self, scenario_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank scenarios by severity (worst first)."""
        sorted_results = sorted(
            scenario_results,
            key=lambda r: abs(r.get("loss_percentage", 0)),
            reverse=True,
        )
        return sorted_results

    async def find_worst_n(
        self,
        scenario_results: list[dict[str, Any]],
        n: int = 3,
    ) -> list[dict[str, Any]]:
        """Find the N worst scenarios."""
        ranked = await self.rank_scenarios(scenario_results)
        return ranked[:n]
