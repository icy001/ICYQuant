"""Stress Score — scores strategy resilience under stress scenarios.

Evaluates how allocations perform under adverse conditions:
- Market crash scenarios
- Volatility spike scenarios
- Liquidity crisis scenarios
- Correlation breakdown scenarios
- Tail event scenarios
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class StressScenarioResult:
    """Result of a single stress scenario."""
    scenario_name: str
    pnl_impact: float = 0.0
    drawdown: float = 0.0
    survival_score: float = 0.0
    passed: bool = True


@dataclass
class StressScoreResult:
    """Stress scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1, higher = more stress resilient
    scenario_results: List[StressScenarioResult] = field(default_factory=list)
    worst_case_drawdown: float = 0.0
    average_drawdown: float = 0.0
    scenarios_passed: int = 0
    scenarios_total: int = 0
    stress_var: float = 0.0
    stress_cvar: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def pass_rate(self) -> float:
        if self.scenarios_total == 0:
            return 1.0
        return self.scenarios_passed / self.scenarios_total

    def summarize(self) -> str:
        return (
            f"StressScore[{self.strategy_id}] score={self.score:.3f} "
            f"pass={self.scenarios_passed}/{self.scenarios_total} "
            f"worst_dd={self.worst_case_drawdown:.2%}"
        )


class StressScorer:
    """Scores strategies based on stress resilience for allocation decisions.

    Runs candidate allocations through pre-defined stress scenarios
    and computes a composite resilience score.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._drawdown_weight = self._config.get("drawdown_weight", 0.35)
        self._pass_rate_weight = self._config.get("pass_rate_weight", 0.25)
        self._cvar_weight = self._config.get("cvar_weight", 0.25)
        self._var_weight = self._config.get("var_weight", 0.15)
        self._max_acceptable_drawdown = self._config.get("max_acceptable_drawdown", 0.25)

    def score(self, strategy_id: str,
              scenario_results: List[Dict[str, Any]],
              stress_var: float = 0.0,
              stress_cvar: float = 0.0) -> StressScoreResult:
        """Compute stress score from scenario results."""
        scenarios = []
        drawdowns = []
        passed_count = 0

        for sr in scenario_results:
            dd = sr.get("drawdown", 0.0)
            passed = dd <= self._max_acceptable_drawdown

            scenarios.append(StressScenarioResult(
                scenario_name=sr.get("name", "unknown"),
                pnl_impact=sr.get("pnl_impact", 0.0),
                drawdown=dd,
                survival_score=sr.get("survival_score", 1.0 - dd / 0.50),
                passed=passed,
            ))
            drawdowns.append(dd)
            if passed:
                passed_count += 1

        worst_dd = max(drawdowns) if drawdowns else 0.0
        avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else 0.0
        pass_rate = passed_count / len(scenarios) if scenarios else 1.0

        # Drawdown score: 0% = perfect, >50% = failed
        dd_score = max(0.0, 1.0 - worst_dd / 0.50)

        # CVaR score
        cvar_score = max(0.0, 1.0 - stress_cvar / 0.15)

        # VaR score
        var_score = max(0.0, 1.0 - stress_var / 0.10)

        score = (
            self._drawdown_weight * dd_score +
            self._pass_rate_weight * pass_rate +
            self._cvar_weight * cvar_score +
            self._var_weight * var_score
        )

        return StressScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, score)),
            scenario_results=scenarios,
            worst_case_drawdown=worst_dd,
            average_drawdown=avg_dd,
            scenarios_passed=passed_count,
            scenarios_total=len(scenarios),
            stress_var=stress_var,
            stress_cvar=stress_cvar,
        )

    def score_default_scenarios(self, strategy_id: str,
                                 base_drawdown: float = 0.10,
                                 correlation_factor: float = 1.0,
                                 liquidity_factor: float = 1.0) -> StressScoreResult:
        """Score against a default set of stress scenarios."""
        default_scenarios = [
            {
                "name": "Market Crash -20%",
                "drawdown": base_drawdown * 2.0 * correlation_factor,
                "pnl_impact": -base_drawdown * 2.0 * correlation_factor,
                "survival_score": 1.0 - base_drawdown * 2.0 * correlation_factor / 0.50,
            },
            {
                "name": "Volatility Spike +100%",
                "drawdown": base_drawdown * 1.5 * correlation_factor,
                "pnl_impact": -base_drawdown * 1.5 * correlation_factor,
                "survival_score": 1.0 - base_drawdown * 1.5 * correlation_factor / 0.50,
            },
            {
                "name": "Liquidity Crisis -50%",
                "drawdown": base_drawdown * 1.8 * liquidity_factor,
                "pnl_impact": -base_drawdown * 1.8 * liquidity_factor,
                "survival_score": 1.0 - base_drawdown * 1.8 * liquidity_factor / 0.50,
            },
            {
                "name": "Correlation Breakdown +50%",
                "drawdown": base_drawdown * 1.8 * correlation_factor,
                "pnl_impact": -base_drawdown * 1.8 * correlation_factor,
                "survival_score": 1.0 - base_drawdown * 1.8 * correlation_factor / 0.50,
            },
            {
                "name": "Tail Risk 5-sigma",
                "drawdown": base_drawdown * 3.0 * correlation_factor,
                "pnl_impact": -base_drawdown * 3.0 * correlation_factor,
                "survival_score": 1.0 - base_drawdown * 3.0 * correlation_factor / 0.50,
            },
        ]
        return self.score(
            strategy_id=strategy_id,
            scenario_results=default_scenarios,
            stress_var=base_drawdown * 1.65,
            stress_cvar=base_drawdown * 2.0,
        )

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[StressScoreResult]:
        """Score multiple strategies at once."""
        results = []
        for sid, params in strategies.items():
            if "scenario_results" in params:
                result = self.score(strategy_id=sid, **params)
            else:
                result = self.score_default_scenarios(strategy_id=sid, **params)
            results.append(result)
        return results
