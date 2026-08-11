"""StressResult — stress test result aggregation and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.stress_engine import StressResult


@dataclass
class StressResultSummary:
    """Summary of multiple stress test results."""

    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0

    avg_loss_pct: float = 0.0
    max_loss_pct: float = 0.0
    min_loss_pct: float = 0.0
    std_loss_pct: float = 0.0

    avg_survival: float = 0.0
    min_survival: float = 100.0

    worst_scenario_name: str = ""
    worst_loss: float = 0.0
    worst_survival: float = 100.0

    scenarios_below_survival_threshold: List[StressResult] = field(default_factory=list)

    capital_erosion_risk: str = "LOW"

    @classmethod
    def from_results(
        cls,
        results: List[StressResult],
        survival_threshold: float = 60.0,
    ) -> "StressResultSummary":
        """Create summary from a list of stress results."""
        import math

        if not results:
            return cls()

        n = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = n - passed

        losses = [abs(r.portfolio_loss_pct) for r in results]
        survivals = [r.survival_score_under_stress for r in results]

        avg_loss = sum(losses) / n
        max_loss = max(losses)
        min_loss = min(losses)
        std_loss = math.sqrt(sum((l - avg_loss) ** 2 for l in losses) / n) if n > 1 else 0.0

        avg_survival = sum(survivals) / n
        min_survival = min(survivals)

        worst = max(results, key=lambda r: abs(r.portfolio_loss_pct))

        below_threshold = [
            r for r in results
            if r.survival_score_under_stress < survival_threshold
        ]

        # capital erosion risk
        erosion = "LOW"
        if max_loss > 30.0:
            erosion = "CRITICAL"
        elif max_loss > 20.0:
            erosion = "HIGH"
        elif max_loss > 10.0:
            erosion = "MODERATE"

        return cls(
            total_scenarios=n,
            passed=passed,
            failed=failed,
            pass_rate=passed / n if n > 0 else 0.0,
            avg_loss_pct=avg_loss,
            max_loss_pct=max_loss,
            min_loss_pct=min_loss,
            std_loss_pct=std_loss,
            avg_survival=avg_survival,
            min_survival=min_survival,
            worst_scenario_name=worst.scenario_name,
            worst_loss=max_loss,
            worst_survival=min_survival,
            scenarios_below_survival_threshold=below_threshold,
            capital_erosion_risk=erosion,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "avg_loss_pct": self.avg_loss_pct,
            "max_loss_pct": self.max_loss_pct,
            "min_loss_pct": self.min_loss_pct,
            "worst_scenario": self.worst_scenario_name,
            "worst_loss_pct": self.worst_loss,
            "worst_survival": self.worst_survival,
            "below_threshold_count": len(self.scenarios_below_survival_threshold),
            "capital_erosion_risk": self.capital_erosion_risk,
        }


class StressResultAnalyzer:
    """Analyzes stress test results for patterns and recommendations."""

    def analyze_strategy_concentration(
        self,
        results: List[StressResult],
        threshold: float = 30.0,
    ) -> Dict[str, Any]:
        """Identify strategies that concentrate stress losses.

        Returns strategies whose loss contribution exceeds the
        threshold percentage in any scenario.
        """
        concentrated: Dict[str, List[str]] = {}

        for result in results:
            total_loss = sum(abs(l) for l in result.strategy_losses.values())
            if total_loss <= 0:
                continue

            for sid, loss in result.strategy_losses.items():
                contribution = abs(loss) / total_loss * 100
                if contribution > threshold:
                    if sid not in concentrated:
                        concentrated[sid] = []
                    concentrated[sid].append(
                        f"{result.scenario_name}: {contribution:.0f}%"
                    )

        return concentrated

    def identify_key_risks(
        self,
        results: List[StressResult],
    ) -> List[str]:
        """Identify key risks from stress results."""
        risks: List[str] = []

        # check for systematic losses across scenarios
        strategy_loss_counts: Dict[str, int] = {}
        for result in results:
            for sid in result.strategy_losses:
                strategy_loss_counts[sid] = strategy_loss_counts.get(sid, 0) + 1

        n = len(results)
        for sid, count in strategy_loss_counts.items():
            if count > n * 0.8:
                risks.append(
                    f"Systematic risk: {sid} consistently contributes to stress losses"
                )

        # check survival erosion
        survivals = [r.survival_score_under_stress for r in results]
        if survivals:
            avg = sum(survivals) / len(survivals)
            if avg < 50:
                risks.append(f"High survival erosion: average stress survival = {avg:.0f}")

        return risks
