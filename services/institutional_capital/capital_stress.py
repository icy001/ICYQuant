"""
Capital Stress — Institutional stress testing for capital pool survival.

Stress scenarios:
    Market Crash, Volatility Spike, Liquidity Collapse,
    Correlation Spike, Execution Cost Spike, Strategy Failure.

Recomputes: Capital Survival under each stress condition.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StressSeverity(str, Enum):
    MODERATE = "moderate"    # 1-in-5-year event
    SEVERE = "severe"        # 1-in-20-year event
    EXTREME = "extreme"      # 1-in-100-year event
    TAIL = "tail"            # historically unprecedented


class StressType(str, Enum):
    MARKET_CRASH = "market_crash"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_COLLAPSE = "liquidity_collapse"
    CORRELATION_SPIKE = "correlation_spike"
    EXECUTION_COST_SPIKE = "execution_cost_spike"
    STRATEGY_FAILURE = "strategy_failure"
    CUSTOM = "custom"


@dataclass
class StressScenario:
    """A capital stress scenario definition."""

    stress_id: str = field(default_factory=lambda: f"SS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    stress_type: StressType = StressType.CUSTOM
    severity: StressSeverity = StressSeverity.MODERATE
    description: str = ""

    # Shock parameters
    equity_return_shock: float = 0.0      # e.g. -0.30 = -30% equity decline
    volatility_shock: float = 0.0          # e.g. 2.0 = 2x normal volatility
    liquidity_reduction: float = 0.0       # e.g. 0.50 = 50% liquidity reduction
    correlation_increase: float = 0.0      # additive to average correlation
    spread_multiplier: float = 1.0         # e.g. 3.0 = 3x normal spreads
    execution_cost_multiplier: float = 1.0

    # Strategy failure
    strategy_failure_count: int = 0
    strategy_failure_drawdown: float = 0.0

    # Result thresholds
    max_acceptable_drawdown: float = 0.25
    min_acceptable_capital_ratio: float = 0.50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stress_id": self.stress_id,
            "name": self.name,
            "type": self.stress_type.value,
            "severity": self.severity.value,
            "equity_return_shock": self.equity_return_shock,
            "volatility_shock": self.volatility_shock,
            "liquidity_reduction": self.liquidity_reduction,
            "correlation_increase": self.correlation_increase,
        }


@dataclass
class StressResult:
    """Outcome of a capital stress test."""

    stress_id: str = ""
    stress_name: str = ""

    # Capital impact
    original_capital: float = 0.0
    stressed_capital: float = 0.0
    capital_loss: float = 0.0
    capital_loss_pct: float = 0.0

    # Portfolio metrics under stress
    stressed_return: float = 0.0
    stressed_risk: float = 0.0
    stressed_drawdown: float = 0.0
    stressed_liquidity: float = 0.0

    # Survival assessment
    survived: bool = True
    capital_ratio: float = 1.0           # stressed / original
    recovery_time_estimate: int = 0      # estimated days to recover
    risk_of_ruin: float = 0.0            # estimated probability

    # Strategy-level impacts
    impacted_strategies: List[str] = field(default_factory=list)
    failed_strategies: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)
    critical: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stress_id": self.stress_id,
            "stress_name": self.stress_name,
            "capital_loss": self.capital_loss,
            "capital_loss_pct": self.capital_loss_pct,
            "stressed_drawdown": self.stressed_drawdown,
            "survived": self.survived,
            "capital_ratio": self.capital_ratio,
            "risk_of_ruin": self.risk_of_ruin,
            "warnings": self.warnings,
            "critical": self.critical,
        }


class CapitalStressTester:
    """Runs capital stress scenarios and assesses survival."""

    def __init__(self):
        self._scenarios: List[StressScenario] = []
        self._results: List[StressResult] = []

    def register(self, scenario: StressScenario) -> None:
        self._scenarios.append(scenario)

    @classmethod
    def regulatory_scenarios(cls) -> List[StressScenario]:
        """Standard regulatory stress scenarios."""
        return [
            StressScenario(
                name="Equity Crash -30%",
                stress_type=StressType.MARKET_CRASH,
                severity=StressSeverity.SEVERE,
                description="Severe equity market decline",
                equity_return_shock=-0.30,
                volatility_shock=2.0,
                correlation_increase=0.15,
                max_acceptable_drawdown=0.30,
            ),
            StressScenario(
                name="Volatility Spike 3x",
                stress_type=StressType.VOLATILITY_SPIKE,
                severity=StressSeverity.SEVERE,
                description="Triple volatility environment",
                volatility_shock=3.0,
                spread_multiplier=2.5,
                execution_cost_multiplier=3.0,
            ),
            StressScenario(
                name="Liquidity Collapse -50%",
                stress_type=StressType.LIQUIDITY_COLLAPSE,
                severity=StressSeverity.SEVERE,
                description="Market liquidity evaporates",
                liquidity_reduction=0.50,
                spread_multiplier=3.0,
                execution_cost_multiplier=4.0,
            ),
            StressScenario(
                name="Correlation Spike +0.30",
                stress_type=StressType.CORRELATION_SPIKE,
                severity=StressSeverity.MODERATE,
                description="All correlations rise — diversification fails",
                correlation_increase=0.30,
                volatility_shock=1.5,
            ),
            StressScenario(
                name="Strategy Failure Cluster",
                stress_type=StressType.STRATEGY_FAILURE,
                severity=StressSeverity.MODERATE,
                description="Multiple strategies fail simultaneously",
                strategy_failure_count=3,
                strategy_failure_drawdown=0.20,
            ),
            StressScenario(
                name="Tail Event — All Shocks",
                stress_type=StressType.CUSTOM,
                severity=StressSeverity.EXTREME,
                description="Combined extreme shock",
                equity_return_shock=-0.20,
                volatility_shock=4.0,
                liquidity_reduction=0.60,
                correlation_increase=0.25,
                execution_cost_multiplier=5.0,
                strategy_failure_count=2,
                strategy_failure_drawdown=0.30,
                max_acceptable_drawdown=0.50,
                min_acceptable_capital_ratio=0.30,
            ),
        ]

    def run(self, scenario: StressScenario, current_capital: float = 100.0,
            current_drawdown: float = 0.05) -> StressResult:
        """Run a single stress scenario."""
        result = StressResult(
            stress_id=scenario.stress_id,
            stress_name=scenario.name,
            original_capital=current_capital,
        )

        # Capital impact from market shock
        capital_impact = current_capital * scenario.equity_return_shock
        strategy_failure_loss = current_capital * scenario.strategy_failure_count * 0.05 * scenario.strategy_failure_drawdown
        result.capital_loss = abs(capital_impact) + abs(strategy_failure_loss)
        result.stressed_capital = current_capital - result.capital_loss
        result.capital_loss_pct = result.capital_loss / max(current_capital, 1.0)
        result.capital_ratio = result.stressed_capital / max(current_capital, 1.0)

        # Risk under stress
        base_risk = 0.15
        result.stressed_risk = base_risk * max(1.0, scenario.volatility_shock) * (1.0 + scenario.correlation_increase)
        result.stressed_drawdown = current_drawdown + abs(scenario.equity_return_shock) * 0.8
        result.stressed_liquidity = max(0.0, 1.0 - scenario.liquidity_reduction)

        # Survival check
        result.survived = (
            result.capital_ratio >= scenario.min_acceptable_capital_ratio and
            result.stressed_drawdown <= scenario.max_acceptable_drawdown
        )

        # Risk of ruin (simplified estimate)
        if result.capital_ratio < 0.20:
            result.risk_of_ruin = 0.15
        elif result.capital_ratio < 0.50:
            result.risk_of_ruin = 0.05
        elif result.capital_ratio < 0.70:
            result.risk_of_ruin = 0.01
        else:
            result.risk_of_ruin = 0.001

        # Recovery estimate
        if result.capital_loss > 0:
            result.recovery_time_estimate = int(result.capital_loss_pct * 252 * 2)

        # Warnings
        if not result.survived:
            result.critical.append(f"Capital ratio {result.capital_ratio:.2f} below minimum {scenario.min_acceptable_capital_ratio:.2f}")
        if result.stressed_drawdown > 0.20:
            result.warnings.append(f"Severe drawdown: {result.stressed_drawdown:.2%}")
        if result.capital_loss_pct > 0.15:
            result.warnings.append(f"Significant capital loss: {result.capital_loss_pct:.2%}")

        self._results.append(result)
        return result

    def run_all(self, current_capital: float = 100.0) -> List[StressResult]:
        results = []
        for s in self._scenarios:
            results.append(self.run(s, current_capital))
        return results

    def summary(self) -> Dict[str, Any]:
        if not self._results:
            return {"error": "No stress tests run"}
        survived = sum(1 for r in self._results if r.survived)
        return {
            "total_tests": len(self._results),
            "survived": survived,
            "failed": len(self._results) - survived,
            "worst_capital_ratio": min(r.capital_ratio for r in self._results),
            "max_drawdown": max(r.stressed_drawdown for r in self._results),
            "max_risk_of_ruin": max(r.risk_of_ruin for r in self._results),
            "details": [r.to_dict() for r in self._results],
        }
