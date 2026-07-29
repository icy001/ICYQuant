from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StressScenario(str, Enum):
    MARKET_CRASH = "MARKET_CRASH"
    LIQUIDITY_FREEZE = "LIQUIDITY_FREEZE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    SECTOR_ROTATION = "SECTOR_ROTATION"
    CORRELATION_BREAKDOWN = "CORRELATION_BREAKDOWN"
    TAIL_EVENT = "TAIL_EVENT"


class StressSeverity(str, Enum):
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"
    CATASTROPHIC = "CATASTROPHIC"


@dataclass
class StressResult:
    scenario: StressScenario
    severity: StressSeverity
    portfolio_loss_pct: float
    max_drawdown: float
    days_to_recover: int
    liquidity_impact: float
    capital_survival: bool
    margin_call_risk: bool
    breach_levels: List[str] = field(default_factory=list)


@dataclass
class StressTestReport:
    report_id: str
    results: List[StressResult]
    worst_case_loss: float
    capital_adequacy: float  # 0-100
    survival_score: float  # 0-100
    critical_vulnerabilities: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    summary: str = ""


class CapitalStressTester:
    """Capital Stress Testing Engine - simulates extreme market scenarios."""

    def __init__(self):
        self.reports: List[StressTestReport] = []
        self.report_count = 0

    def simulate(self, scenario):
        """Run capital stress test simulation.

        Args:
            scenario: Scenario data (str, dict, or StressTestReport).

        Returns:
            Dict containing stress test results.
        """
        if isinstance(scenario, StressTestReport):
            return self._process_report(scenario)
        if isinstance(scenario, dict):
            return self._simulate_dict(scenario)
        return {"scenario": scenario}

    def _process_report(self, report: StressTestReport) -> dict:
        self.reports.append(report)
        return self._to_dict(report)

    def _simulate_dict(self, data: dict) -> dict:
        self.report_count += 1

        total_capital = data.get("total_capital", data.get("aum", 1000000.0))
        current_exposure = data.get("current_exposure", data.get("exposure", 0.6))
        leverage = data.get("leverage", 1.0)
        cash_ratio = data.get("cash_ratio", 0.10)
        concentration = data.get("concentration", 0.3)

        # Run scenarios
        results = self._run_scenarios(total_capital, current_exposure, leverage, cash_ratio, concentration)

        # Aggregate
        worst = max(r.portfolio_loss_pct for r in results)
        capital_adequacy = self._calc_capital_adequacy(results, total_capital, cash_ratio)
        survival_score = self._calc_survival_score(results)
        vulnerabilities = self._identify_vulnerabilities(results, leverage, concentration)
        recommendations = self._generate_recommendations(results, vulnerabilities)

        report = StressTestReport(
            report_id=f"STRESS_{self.report_count:04d}",
            results=results,
            worst_case_loss=round(worst, 4),
            capital_adequacy=round(capital_adequacy, 1),
            survival_score=round(survival_score, 1),
            critical_vulnerabilities=vulnerabilities,
            recommendations=recommendations,
            summary=self._summarize(worst, capital_adequacy, survival_score),
        )
        self.reports.append(report)
        return self._to_dict(report)

    def _run_scenarios(
        self, capital: float, exposure: float, leverage: float, cash: float, concentration: float
    ) -> List[StressResult]:
        scenarios = []

        # Market Crash (-30%)
        crash_loss = exposure * 0.30 * leverage
        scenarios.append(StressResult(
            scenario=StressScenario.MARKET_CRASH,
            severity=StressSeverity.SEVERE,
            portfolio_loss_pct=round(crash_loss, 4),
            max_drawdown=round(crash_loss * 1.2, 4),
            days_to_recover=180,
            liquidity_impact=0.6,
            capital_survival=cash > crash_loss,
            margin_call_risk=leverage > 1.5 and crash_loss > 0.15,
            breach_levels=self._check_breaches(crash_loss, "Market Crash -30%"),
        ))

        # Liquidity Freeze
        freeze_loss = exposure * 0.20 * leverage
        scenarios.append(StressResult(
            scenario=StressScenario.LIQUIDITY_FREEZE,
            severity=StressSeverity.EXTREME,
            portfolio_loss_pct=round(freeze_loss, 4),
            max_drawdown=round(freeze_loss * 1.5, 4),
            days_to_recover=365,
            liquidity_impact=0.9,
            capital_survival=cash > freeze_loss * 1.5,
            margin_call_risk=leverage > 1.2,
            breach_levels=self._check_breaches(freeze_loss, "Liquidity Freeze"),
        ))

        # High Volatility
        vol_loss = exposure * 0.15 * leverage
        scenarios.append(StressResult(
            scenario=StressScenario.HIGH_VOLATILITY,
            severity=StressSeverity.MODERATE,
            portfolio_loss_pct=round(vol_loss, 4),
            max_drawdown=round(vol_loss * 1.3, 4),
            days_to_recover=90,
            liquidity_impact=0.3,
            capital_survival=True,
            margin_call_risk=leverage > 2.0 and vol_loss > 0.10,
            breach_levels=self._check_breaches(vol_loss, "High Volatility"),
        ))

        # Correlation Breakdown
        corr_loss = concentration * 0.35 * leverage
        scenarios.append(StressResult(
            scenario=StressScenario.CORRELATION_BREAKDOWN,
            severity=StressSeverity.SEVERE,
            portfolio_loss_pct=round(corr_loss, 4),
            max_drawdown=round(corr_loss * 1.4, 4),
            days_to_recover=120,
            liquidity_impact=0.5,
            capital_survival=cash > corr_loss * 1.2,
            margin_call_risk=concentration > 0.5 and corr_loss > 0.15,
            breach_levels=self._check_breaches(corr_loss, "Correlation Breakdown"),
        ))

        # Tail Event (Black Swan)
        tail_loss = exposure * 0.40 * leverage
        scenarios.append(StressResult(
            scenario=StressScenario.TAIL_EVENT,
            severity=StressSeverity.CATASTROPHIC,
            portfolio_loss_pct=round(tail_loss, 4),
            max_drawdown=round(tail_loss * 1.8, 4),
            days_to_recover=730,
            liquidity_impact=0.95,
            capital_survival=cash > tail_loss,
            margin_call_risk=True,
            breach_levels=self._check_breaches(tail_loss, "Tail Event (Black Swan)"),
        ))

        return scenarios

    def _check_breaches(self, loss_pct: float, label: str) -> List[str]:
        breaches = []
        if loss_pct > 0.05:
            breaches.append(f"[{label}] Loss exceeds 5% threshold")
        if loss_pct > 0.10:
            breaches.append(f"[{label}] Loss exceeds 10% risk limit")
        if loss_pct > 0.20:
            breaches.append(f"[{label}] CRITICAL: Loss exceeds 20% maximum tolerance")
        return breaches

    def _calc_capital_adequacy(self, results: List[StressResult], capital: float, cash: float) -> float:
        survived = sum(1 for r in results if r.capital_survival)
        return (survived / len(results)) * 100

    def _calc_survival_score(self, results: List[StressResult]) -> float:
        weights = {
            StressScenario.MARKET_CRASH: 25,
            StressScenario.LIQUIDITY_FREEZE: 25,
            StressScenario.HIGH_VOLATILITY: 10,
            StressScenario.CORRELATION_BREAKDOWN: 15,
            StressScenario.TAIL_EVENT: 25,
        }
        total = sum(weights.get(r.scenario, 0) for r in results)
        if total == 0:
            return 0
        survived = sum(weights.get(r.scenario, 0) for r in results if r.capital_survival)
        return (survived / total) * 100

    def _identify_vulnerabilities(self, results: List[StressResult], leverage: float, concentration: float) -> List[str]:
        vulns = []
        for r in results:
            if not r.capital_survival:
                vulns.append(f"Capital insufficient to survive: {r.scenario.value}")
            if r.margin_call_risk:
                vulns.append(f"Margin call risk in: {r.scenario.value}")
        if leverage > 1.5:
            vulns.append(f"High leverage ({leverage:.1f}x) amplifies all stress losses")
        if concentration > 0.4:
            vulns.append(f"High concentration ({concentration:.0%}) increases correlation breakdown risk")
        return vulns

    def _generate_recommendations(self, results: List[StressResult], vulns: List[str]) -> List[str]:
        recs = []
        crash = next((r for r in results if r.scenario == StressScenario.MARKET_CRASH), None)
        if crash and not crash.capital_survival:
            recs.append("Increase cash reserves to survive market crash scenario")
        if crash and crash.margin_call_risk:
            recs.append("Reduce leverage to avoid margin calls in stress scenarios")

        tail = next((r for r in results if r.scenario == StressScenario.TAIL_EVENT), None)
        if tail and not tail.capital_survival:
            recs.append("Implement tail-risk hedging (put options, VIX futures)")

        if not recs:
            recs.append("Capital structure is resilient to stress scenarios")
        return recs

    def _summarize(self, worst_loss: float, adequacy: float, survival: float) -> str:
        status = "RESILIENT" if survival >= 60 else "VULNERABLE" if survival >= 30 else "AT RISK"
        return (
            f"Stress Test: {status}. "
            f"Worst case loss: {worst_loss:.0%}, "
            f"Capital adequacy: {adequacy:.0f}%, "
            f"Survival score: {survival:.0f}/100"
        )

    def _to_dict(self, report: StressTestReport) -> dict:
        return {
            "scenario": {
                "report_id": report.report_id,
                "results": [
                    {
                        "scenario": r.scenario.value,
                        "severity": r.severity.value,
                        "portfolio_loss_pct": r.portfolio_loss_pct,
                        "max_drawdown": r.max_drawdown,
                        "days_to_recover": r.days_to_recover,
                        "liquidity_impact": r.liquidity_impact,
                        "capital_survival": r.capital_survival,
                        "margin_call_risk": r.margin_call_risk,
                        "breach_levels": r.breach_levels,
                    }
                    for r in report.results
                ],
                "worst_case_loss": report.worst_case_loss,
                "capital_adequacy": report.capital_adequacy,
                "survival_score": report.survival_score,
                "critical_vulnerabilities": report.critical_vulnerabilities,
                "recommendations": report.recommendations,
                "summary": report.summary,
            }
        }

    def get_report(self) -> Optional[StressTestReport]:
        """Get the latest stress test report."""
        return self.reports[-1] if self.reports else None
