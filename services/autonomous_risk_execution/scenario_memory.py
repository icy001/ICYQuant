"""
Scenario Memory — persistent storage of scenario analysis and stress testing results.

Stores complete scenario and stress test records for:
    - Retrospective analysis of portfolio resilience
    - Model calibration against historical scenarios
    - Worst-case and best-case identification per portfolio
    - Aggregate statistics and pass/fail tracking
    - Audit trail for risk governance and compliance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Classification of scenario analysis types."""

    HISTORICAL = "historical"
    HYPOTHETICAL = "hypothetical"
    MONTE_CARLO = "monte_carlo"
    REGIME_CHANGE = "regime_change"
    FLASH_CRASH = "flash_crash"
    RATE_SHOCK = "rate_shock"
    CREDIT_CRISIS = "credit_crisis"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    GEOPOLITICAL = "geopolitical"
    PANDEMIC = "pandemic"


class RiskLevel(Enum):
    """Risk severity level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class StressTestType(Enum):
    """Classification of stress test categories."""

    VAR_STRESS = "var_stress"
    ES_STRESS = "es_stress"
    LIQUIDITY_STRESS = "liquidity_stress"
    LEVERAGE_STRESS = "leverage_stress"
    CONCENTRATION_STRESS = "concentration_stress"
    CORRELATION_STRESS = "correlation_stress"
    REGIME_STRESS = "regime_stress"


@dataclass
class ScenarioAnalysis:
    """
    A complete scenario analysis record.

    Captures the full output of a scenario analysis run including
    the type of scenario, its impact on the portfolio, and key
    risk metric changes for retrospective review.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    scenario_name: str = ""
    scenario_type: ScenarioType = ScenarioType.HYPOTHETICAL
    description: str = ""
    impact_pct: float = 0.0
    affected_assets: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    var_change: float = 0.0
    es_change: float = 0.0
    max_drawdown: float = 0.0
    recovery_probability: float = 0.0
    duration_days: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StressTestResult:
    """
    A complete stress test result record.

    Captures the output of a single stress test including
    severity, capital impact, liquidity implications, and
    the pass/fail determination with recommendations.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    test_name: str = ""
    test_type: StressTestType = StressTestType.VAR_STRESS
    severity_pct: float = 0.0
    capital_impact_pct: float = 0.0
    liquidity_impact_pct: float = 0.0
    leverage_impact: float = 0.0
    concentration_impact: float = 0.0
    pass_fail: bool = True
    recommendations: list[str] = field(default_factory=list)


@dataclass
class ScenarioMemoryStats:
    """
    Aggregate statistics from the scenario memory.

    Provides a summary view of all stored scenarios and stress tests
    including pass rates, average impacts, and breakdowns by type
    and severity for risk governance reporting.
    """

    total_scenarios: int = 0
    total_stress_tests: int = 0
    pass_rate_pct: float = 0.0
    avg_impact_pct: float = 0.0
    worst_scenario: Optional[str] = None
    by_type: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)


class ScenarioMemory:
    """
    Persistent storage for scenario analysis and stress testing results.

    Stores and indexes scenario analysis and stress test results for:
        - Retrospective analysis of portfolio risk resilience
        - Model calibration against historical performance
        - Worst-case and best-case scenario identification per portfolio
        - Aggregate statistics for risk governance and reporting
        - Audit trail for regulatory compliance

    Usage:
        memory = ScenarioMemory(max_scenarios=500, max_stress_tests=300)
        scenario_id = await memory.store_scenario(analysis)
        stress_id = await memory.store_stress_test(result)
        history = await memory.get_scenario_history(portfolio_id="p1")
        worst = await memory.get_worst_case(portfolio_id="p1")
        stats = await memory.get_stats()
    """

    def __init__(self, max_scenarios: int = 500, max_stress_tests: int = 300) -> None:
        self._max_scenarios = max_scenarios
        self._max_stress_tests = max_stress_tests
        self._scenarios: list[ScenarioAnalysis] = []
        self._stress_tests: list[StressTestResult] = []
        self._total_scenarios_stored: int = 0
        self._total_stress_tests_stored: int = 0

    async def store_scenario(self, scenario: ScenarioAnalysis) -> str:
        """
        Store a scenario analysis result.

        Appends the scenario to memory and trims old entries when
        the maximum capacity is reached, preserving the most recent
        half of the entries.

        Args:
            scenario: The scenario analysis to store.

        Returns:
            The unique identifier of the stored scenario.
        """
        self._scenarios.append(scenario)
        self._total_scenarios_stored += 1

        if len(self._scenarios) > self._max_scenarios:
            self._scenarios = self._scenarios[-self._max_scenarios // 2:]

        logger.info(
            "Stored scenario %s (type=%s, impact=%.2f%%, risk=%s)",
            scenario.id, scenario.scenario_type.value,
            scenario.impact_pct, scenario.risk_level.value,
        )
        return scenario.id

    async def store_stress_test(self, stress_test: StressTestResult) -> str:
        """
        Store a stress test result.

        Appends the stress test to memory and trims old entries when
        the maximum capacity is reached, preserving the most recent
        half of the entries.

        Args:
            stress_test: The stress test result to store.

        Returns:
            The unique identifier of the stored stress test.
        """
        self._stress_tests.append(stress_test)
        self._total_stress_tests_stored += 1

        if len(self._stress_tests) > self._max_stress_tests:
            self._stress_tests = self._stress_tests[-self._max_stress_tests // 2:]

        logger.info(
            "Stored stress test %s (type=%s, severity=%.2f%%, pass=%s)",
            stress_test.id, stress_test.test_type.value,
            stress_test.severity_pct, stress_test.pass_fail,
        )
        return stress_test.id

    async def get_scenario_history(
        self,
        portfolio_id: str = "",
        scenario_type: str = "",
        limit: int = 50,
    ) -> list[ScenarioAnalysis]:
        """
        Retrieve scenario analysis history with optional filters.

        Args:
            portfolio_id: Filter by portfolio identifier (empty = all).
            scenario_type: Filter by scenario type name (empty = all).
            limit: Maximum number of records to return.

        Returns:
            A list of scenario analysis records, most recent first.
        """
        results = self._scenarios

        if portfolio_id:
            results = [s for s in results if s.portfolio_id == portfolio_id]
        if scenario_type:
            results = [s for s in results if s.scenario_type.value == scenario_type]

        return list(reversed(results[-limit:]))

    async def get_stress_history(
        self,
        portfolio_id: str = "",
        limit: int = 50,
    ) -> list[StressTestResult]:
        """
        Retrieve stress test history with optional filters.

        Args:
            portfolio_id: Filter by portfolio identifier (empty = all).
            limit: Maximum number of records to return.

        Returns:
            A list of stress test result records, most recent first.
        """
        results = self._stress_tests

        if portfolio_id:
            results = [s for s in results if s.portfolio_id == portfolio_id]

        return list(reversed(results[-limit:]))

    async def get_worst_case(self, portfolio_id: str) -> Optional[ScenarioAnalysis]:
        """
        Identify the worst-case scenario for a given portfolio.

        Returns the scenario with the highest absolute impact percentage
        from the stored history for the specified portfolio.

        Args:
            portfolio_id: The portfolio identifier to query.

        Returns:
            The scenario analysis with the worst impact, or None if
            no scenarios are stored for this portfolio.
        """
        portfolio_scenarios = [
            s for s in self._scenarios if s.portfolio_id == portfolio_id
        ]

        if not portfolio_scenarios:
            return None

        return max(portfolio_scenarios, key=lambda s: abs(s.impact_pct))

    async def get_best_case(self, portfolio_id: str) -> Optional[ScenarioAnalysis]:
        """
        Identify the best-case (least impactful) scenario for a portfolio.

        Returns the scenario with the lowest absolute impact percentage
        from the stored history for the specified portfolio.

        Args:
            portfolio_id: The portfolio identifier to query.

        Returns:
            The scenario analysis with the least impact, or None if
            no scenarios are stored for this portfolio.
        """
        portfolio_scenarios = [
            s for s in self._scenarios if s.portfolio_id == portfolio_id
        ]

        if not portfolio_scenarios:
            return None

        return min(portfolio_scenarios, key=lambda s: abs(s.impact_pct))

    async def calibrate_models(self) -> dict[str, Any]:
        """
        Perform model calibration analysis using stored scenarios.

        Analyzes historical scenario results to compute calibration
        factors that can be applied to risk models, adjusting their
        parameters based on observed scenario outcomes.

        Returns:
            A dictionary containing calibration factors including
            volatility scaling, correlation adjustments, and
            liquidity adjustment recommendations.
        """
        if not self._scenarios:
            return {
                "status": "insufficient_data",
                "message": "No scenario data available for calibration",
                "sample_size": 0,
            }

        impacts = [s.impact_pct for s in self._scenarios]
        var_changes = [s.var_change for s in self._scenarios]
        es_changes = [s.es_change for s in self._scenarios]
        drawdowns = [s.max_drawdown for s in self._scenarios]

        n = len(impacts)
        avg_impact = sum(impacts) / n
        avg_var = sum(var_changes) / n if var_changes else 0.0
        avg_es = sum(es_changes) / n if es_changes else 0.0
        avg_drawdown = sum(drawdowns) / n if drawdowns else 0.0

        impact_variance = sum((x - avg_impact) ** 2 for x in impacts) / n if n > 1 else 0.0
        impact_std = impact_variance ** 0.5

        type_counts: dict[str, int] = {}
        for s in self._scenarios:
            t = s.scenario_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        calibration = {
            "status": "calibrated",
            "sample_size": n,
            "avg_impact_pct": round(avg_impact, 4),
            "impact_std_pct": round(impact_std, 4),
            "avg_var_change": round(avg_var, 4),
            "avg_es_change": round(avg_es, 4),
            "avg_max_drawdown": round(avg_drawdown, 4),
            "volatility_scaling_factor": round(1.0 + avg_impact, 4),
            "correlation_adjustment": round(avg_var * 0.1, 4),
            "liquidity_adjustment": round(avg_drawdown * 0.2, 4),
            "scenario_type_distribution": type_counts,
            "recommendations": self._generate_calibration_recommendations(
                avg_impact, impact_std, avg_drawdown, n
            ),
        }

        logger.info(
            "Model calibration complete: %d samples, avg_impact=%.4f, std=%.4f",
            n, avg_impact, impact_std,
        )
        return calibration

    async def get_stats(self) -> ScenarioMemoryStats:
        """
        Compute aggregate statistics from all stored scenarios and stress tests.

        Calculates pass rates, average impacts, worst-case scenario
        identification, and breakdowns by scenario type and risk severity.

        Returns:
            A ScenarioMemoryStats instance with aggregate metrics.
        """
        stats = ScenarioMemoryStats(
            total_scenarios=len(self._scenarios),
            total_stress_tests=len(self._stress_tests),
        )

        if self._stress_tests:
            passed = sum(1 for s in self._stress_tests if s.pass_fail)
            stats.pass_rate_pct = round(
                (passed / len(self._stress_tests)) * 100, 2
            )

        if self._scenarios:
            impacts = [s.impact_pct for s in self._scenarios]
            stats.avg_impact_pct = round(sum(impacts) / len(impacts), 4)

            worst = max(self._scenarios, key=lambda s: abs(s.impact_pct))
            stats.worst_scenario = worst.scenario_name or worst.id

            type_counts: dict[str, int] = {}
            for s in self._scenarios:
                t = s.scenario_type.value
                type_counts[t] = type_counts.get(t, 0) + 1
            stats.by_type = type_counts

            severity_counts: dict[str, int] = {}
            for s in self._scenarios:
                sev = s.risk_level.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            stats.by_severity = severity_counts

        return stats

    async def clear_portfolio(self, portfolio_id: str) -> None:
        """
        Remove all scenarios and stress tests for a specific portfolio.

        This operation is irreversible. Use with caution.

        Args:
            portfolio_id: The portfolio identifier whose records
                should be removed.
        """
        before_scenarios = len(self._scenarios)
        before_stress = len(self._stress_tests)

        self._scenarios = [
            s for s in self._scenarios if s.portfolio_id != portfolio_id
        ]
        self._stress_tests = [
            s for s in self._stress_tests if s.portfolio_id != portfolio_id
        ]

        removed_scenarios = before_scenarios - len(self._scenarios)
        removed_stress = before_stress - len(self._stress_tests)

        logger.info(
            "Cleared portfolio %s: removed %d scenarios, %d stress tests",
            portfolio_id, removed_scenarios, removed_stress,
        )

    def _generate_calibration_recommendations(
        self,
        avg_impact: float,
        impact_std: float,
        avg_drawdown: float,
        sample_size: int,
    ) -> list[str]:
        """
        Generate actionable calibration recommendations from analysis metrics.

        Args:
            avg_impact: Average scenario impact percentage.
            impact_std: Standard deviation of scenario impacts.
            avg_drawdown: Average maximum drawdown observed.
            sample_size: Number of scenarios analyzed.

        Returns:
            A list of recommendation strings.
        """
        recommendations: list[str] = []

        if sample_size < 10:
            recommendations.append(
                "Collect more scenario data (target: 10+ scenarios) "
                "for more reliable calibration"
            )

        if abs(avg_impact) > 0.05:
            recommendations.append(
                f"Average impact ({avg_impact:.2%}) exceeds 5% threshold; "
                "consider adjusting volatility assumptions upward"
            )

        if impact_std > 0.10:
            recommendations.append(
                f"High impact volatility (std={impact_std:.2%}) indicates "
                "regime uncertainty; consider wider risk bands"
            )

        if avg_drawdown > 0.10:
            recommendations.append(
                f"Average max drawdown ({avg_drawdown:.2%}) is significant; "
                "stress-test with more conservative parameters"
            )

        if not recommendations:
            recommendations.append(
                "Calibration within normal parameters; no adjustments needed"
            )

        return recommendations

    @property
    def total_scenarios_stored(self) -> int:
        """Total number of scenario analysis records stored."""
        return self._total_scenarios_stored

    @property
    def total_stress_tests_stored(self) -> int:
        """Total number of stress test records stored."""
        return self._total_stress_tests_stored

    @property
    def scenario_count(self) -> int:
        """Current number of scenario records in memory."""
        return len(self._scenarios)

    @property
    def stress_test_count(self) -> int:
        """Current number of stress test records in memory."""
        return len(self._stress_tests)