from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class StressScenario:
    name: str
    description: str
    market_shock_pct: float
    volatility_multiplier: float
    liquidity_reduction: float
    credit_spread_widening: float
    duration_days: int


@dataclass
class StressTestResult:
    scenario_name: str
    estimated_loss_pct: float
    max_drawdown_pct: float
    var_99: float
    capital_impact_pct: float
    passed: bool
    warnings: List[str]


class StressTestingEngine:
    def __init__(self):
        self.scenarios: Dict[str, StressScenario] = {
            "market_crash": StressScenario(
                name="market_crash",
                description="Broad equity market crash",
                market_shock_pct=-0.20,
                volatility_multiplier=3.0,
                liquidity_reduction=0.5,
                credit_spread_widening=0.03,
                duration_days=10,
            ),
            "recession": StressScenario(
                name="recession",
                description="Economic recession scenario",
                market_shock_pct=-0.12,
                volatility_multiplier=2.0,
                liquidity_reduction=0.3,
                credit_spread_widening=0.05,
                duration_days=90,
            ),
            "rate_shock": StressScenario(
                name="rate_shock",
                description="Interest rate shock",
                market_shock_pct=-0.08,
                volatility_multiplier=2.5,
                liquidity_reduction=0.2,
                credit_spread_widening=0.02,
                duration_days=30,
            ),
            "liquidity_crisis": StressScenario(
                name="liquidity_crisis",
                description="Liquidity crisis",
                market_shock_pct=-0.15,
                volatility_multiplier=4.0,
                liquidity_reduction=0.8,
                credit_spread_widening=0.04,
                duration_days=15,
            ),
            "currency_devaluation": StressScenario(
                name="currency_devaluation",
                description="Currency devaluation",
                market_shock_pct=-0.10,
                volatility_multiplier=2.2,
                liquidity_reduction=0.4,
                credit_spread_widening=0.06,
                duration_days=20,
            ),
        }

    def add_scenario(self, scenario: StressScenario):
        self.scenarios[scenario.name] = scenario

    def run_stress_test(
        self,
        portfolio_value: float = 1000000,
        holdings: Dict[str, float] = None,
        scenario_name: str = "market_crash",
        capital_threshold: float = 0.05,
    ) -> StressTestResult:
        holdings = holdings or {"equity": 0.6, "fixed_income": 0.3, "cash": 0.1}
        scenario = self.scenarios.get(scenario_name)

        if not scenario:
            return StressTestResult(
                scenario_name=scenario_name,
                estimated_loss_pct=0.0,
                max_drawdown_pct=0.0,
                var_99=0.0,
                capital_impact_pct=0.0,
                passed=True,
                warnings=[f"Scenario {scenario_name} not found"],
            )

        equity_loss = holdings.get("equity", 0) * scenario.market_shock_pct
        fi_loss = holdings.get("fixed_income", 0) * scenario.credit_spread_widening * -1
        total_loss_pct = equity_loss + fi_loss
        total_loss = portfolio_value * total_loss_pct

        var_99 = abs(total_loss_pct) * 0.8
        capital_impact = abs(total_loss_pct) * 1.5
        max_drawdown = abs(total_loss_pct) * 1.2

        passed = capital_impact <= capital_threshold

        warnings = []
        if not passed:
            warnings.append(
                f"Capital impact {capital_impact:.2%} exceeds threshold {capital_threshold:.2%}"
            )
        if scenario.volatility_multiplier > 2.5:
            warnings.append(
                f"High volatility multiplier: {scenario.volatility_multiplier}"
            )
        if scenario.liquidity_reduction > 0.5:
            warnings.append(
                f"Severe liquidity reduction: {scenario.liquidity_reduction:.0%}"
            )

        return StressTestResult(
            scenario_name=scenario_name,
            estimated_loss_pct=round(total_loss_pct, 6),
            max_drawdown_pct=round(max_drawdown, 6),
            var_99=round(var_99, 6),
            capital_impact_pct=round(capital_impact, 6),
            passed=passed,
            warnings=warnings,
        )

    def list_scenarios(self) -> List[str]:
        return list(self.scenarios.keys())
