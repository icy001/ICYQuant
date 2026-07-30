from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ScenarioDefinition:
    name: str
    description: str
    market_change: float
    sector_shocks: Dict[str, float]
    duration_days: int


@dataclass
class ScenarioResult:
    scenario_name: str
    portfolio_pnl_pct: float
    max_drawdown_pct: float
    sector_impacts: Dict[str, float]
    risk_level: str


class ScenarioEngine:
    def __init__(self):
        self.scenarios: Dict[str, ScenarioDefinition] = {
            "COVID2020": ScenarioDefinition(
                name="COVID2020",
                description="COVID-19 pandemic market shock",
                market_change=-0.34,
                sector_shocks={
                    "energy": -0.55,
                    "travel": -0.50,
                    "technology": -0.25,
                    "financial": -0.40,
                    "healthcare": -0.10,
                    "consumer": -0.30,
                },
                duration_days=30,
            ),
            "FedHiking2022": ScenarioDefinition(
                name="FedHiking2022",
                description="Federal Reserve aggressive rate hiking",
                market_change=-0.25,
                sector_shocks={
                    "technology": -0.35,
                    "financial": 0.05,
                    "real_estate": -0.30,
                    "consumer": -0.20,
                    "energy": 0.10,
                },
                duration_days=180,
            ),
            "AIRally2024": ScenarioDefinition(
                name="AIRally2024",
                description="AI sector rally scenario",
                market_change=0.15,
                sector_shocks={
                    "technology": 0.45,
                    "semiconductors": 0.50,
                    "financial": 0.05,
                    "energy": -0.05,
                },
                duration_days=90,
            ),
            "FlashCrash": ScenarioDefinition(
                name="FlashCrash",
                description="Flash crash scenario",
                market_change=-0.15,
                sector_shocks={
                    "technology": -0.20,
                    "financial": -0.18,
                    "energy": -0.12,
                    "cash": 0.0,
                },
                duration_days=1,
            ),
            "AIBubbleBurst": ScenarioDefinition(
                name="AIBubbleBurst",
                description="AI bubble burst scenario",
                market_change=-0.12,
                sector_shocks={
                    "technology": -0.40,
                    "semiconductors": -0.45,
                    "financial": -0.05,
                    "energy": 0.02,
                    "consumer": -0.08,
                },
                duration_days=45,
            ),
            "SemiconductorCollapse": ScenarioDefinition(
                name="SemiconductorCollapse",
                description="Semiconductor sector collapse",
                market_change=-0.08,
                sector_shocks={
                    "semiconductors": -0.50,
                    "technology": -0.20,
                    "financial": -0.03,
                },
                duration_days=30,
            ),
            "OilShock": ScenarioDefinition(
                name="OilShock",
                description="Oil price shock",
                market_change=-0.10,
                sector_shocks={
                    "energy": 0.30,
                    "airlines": -0.25,
                    "consumer": -0.15,
                    "automotive": -0.20,
                },
                duration_days=60,
            ),
        }

    def add_scenario(self, scenario: ScenarioDefinition):
        self.scenarios[scenario.name] = scenario

    def run_scenario(
        self,
        scenario_name: str,
        portfolio_sector_weights: Dict[str, float] = None,
    ) -> ScenarioResult:
        weights = portfolio_sector_weights or {}
        scenario = self.scenarios.get(scenario_name)

        if not scenario:
            return ScenarioResult(
                scenario_name=scenario_name,
                portfolio_pnl_pct=0.0,
                max_drawdown_pct=0.0,
                sector_impacts={},
                risk_level="UNKNOWN",
            )

        sector_impacts = {}
        total_pnl = 0.0

        for sector, weight in weights.items():
            shock = scenario.sector_shocks.get(sector, scenario.market_change * 0.5)
            impact = weight * shock
            sector_impacts[sector] = round(impact, 6)
            total_pnl += impact

        max_drawdown = abs(total_pnl) * 1.3

        if abs(total_pnl) > 0.15:
            risk_level = "CRITICAL"
        elif abs(total_pnl) > 0.10:
            risk_level = "HIGH"
        elif abs(total_pnl) > 0.05:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return ScenarioResult(
            scenario_name=scenario_name,
            portfolio_pnl_pct=round(total_pnl, 6),
            max_drawdown_pct=round(max_drawdown, 6),
            sector_impacts=sector_impacts,
            risk_level=risk_level,
        )

    def list_scenarios(self) -> List[str]:
        return list(self.scenarios.keys())
