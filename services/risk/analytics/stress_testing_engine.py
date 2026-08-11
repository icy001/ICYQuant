"""
Stress Testing Engine — Runs portfolio stress tests against historical and custom scenarios.

Evaluates portfolio resilience under extreme market conditions by applying
scenario-based shocks and computing impact on positions and capital.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StressScenario:
    """A stress testing scenario definition."""
    scenario_id: str
    name: str
    description: str
    category: str = "custom"  # historical, macro, market, custom
    shocks: dict[str, float] = field(default_factory=dict)
    # shocks: {asset: price_change_pct, ...}
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StressTestResult:
    """Result of a single scenario stress test."""
    scenario_id: str
    scenario_name: str
    pre_shock_value: float
    post_shock_value: float
    absolute_loss: float
    loss_percentage: float
    positions_affected: int
    breached_limits: list[str]
    risk_level: str  # low, medium, high, critical
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class StressTestingEngine:
    """
    Stress testing engine for portfolio risk analysis.

    Applies predefined and custom market shock scenarios to portfolio
    data and computes the projected impact on portfolio value, PnL,
    and risk limits.

    Supports:
    - Historical scenario replay (2008, COVID, etc.)
    - Custom user-defined shocks
    - Macro-economic scenarios
    - Multi-asset correlated shocks
    - Worst-case loss estimation

    Usage::

        engine = StressTestingEngine()
        await engine.initialize()
        results = await engine.run_stress_tests(portfolio_data)
    """

    def __init__(self, scenarios: Optional[list[StressScenario]] = None) -> None:
        self._scenarios: dict[str, StressScenario] = {}
        self._initialized = False
        self._default_scenarios_loaded = False
        if scenarios:
            for s in scenarios:
                self._scenarios[s.scenario_id] = s

    async def initialize(self) -> None:
        """Initialize and load default scenarios."""
        if self._initialized:
            return
        if not self._default_scenarios_loaded:
            await self._load_default_scenarios()
            self._default_scenarios_loaded = True
        self._initialized = True
        logger.info(f"StressTestingEngine initialized with {len(self._scenarios)} scenarios.")

    # ---- Core API ----

    async def run_stress_tests(
        self,
        portfolio_data: dict[str, Any],
        scenario_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Run stress tests against the portfolio.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio with positions, balances, and market data.
        scenario_ids : list[str], optional
            Specific scenarios to test. Defaults to all.

        Returns
        -------
        dict
            Stress test results with per-scenario impact.
        """
        if not self._initialized:
            await self.initialize()

        scenarios = (
            [self._scenarios[sid] for sid in scenario_ids if sid in self._scenarios]
            if scenario_ids
            else list(self._scenarios.values())
        )

        if not scenarios:
            return {"status": "no_scenarios", "results": []}

        positions = portfolio_data.get("positions", [])
        total_value = portfolio_data.get("total_value", 0.0)
        if total_value <= 0:
            total_value = sum(
                abs(p.get("market_value", 0)) for p in positions
                if isinstance(p, dict)
            )

        # Run scenarios in parallel
        tasks = [
            asyncio.create_task(self._run_single_scenario(scenario, positions, total_value))
            for scenario in scenarios
        ]
        scenario_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[dict] = []
        worst_loss = 0.0
        worst_scenario = ""

        for i, res in enumerate(scenario_results):
            if isinstance(res, Exception):
                results.append({
                    "scenario_id": scenarios[i].scenario_id,
                    "scenario_name": scenarios[i].name,
                    "error": str(res),
                })
                continue

            result: StressTestResult = res
            results.append({
                "scenario_id": result.scenario_id,
                "scenario_name": result.scenario_name,
                "pre_shock_value": result.pre_shock_value,
                "post_shock_value": result.post_shock_value,
                "absolute_loss": result.absolute_loss,
                "loss_percentage": result.loss_percentage,
                "positions_affected": result.positions_affected,
                "breached_limits": result.breached_limits,
                "risk_level": result.risk_level,
            })

            if result.loss_percentage < worst_loss:
                worst_loss = result.loss_percentage
                worst_scenario = result.scenario_name

        # Compute summary
        passed = sum(1 for r in results if r.get("risk_level") in ("low", "medium"))
        failed = sum(1 for r in results if r.get("risk_level") in ("high", "critical"))

        return {
            "total_scenarios": len(results),
            "passed": passed,
            "failed": failed,
            "worst_case_loss_pct": abs(worst_loss),
            "worst_case_scenario": worst_scenario,
            "results": results,
        }

    async def run_custom_stress_tests(
        self,
        portfolio_data: dict[str, Any],
        scenarios: list[StressScenario],
    ) -> dict[str, Any]:
        """Run stress tests with custom scenarios."""
        positions = portfolio_data.get("positions", [])
        total_value = portfolio_data.get("total_value", 0.0)
        if total_value <= 0:
            total_value = sum(
                abs(p.get("market_value", 0)) for p in positions
                if isinstance(p, dict)
            )

        tasks = [
            asyncio.create_task(self._run_single_scenario(s, positions, total_value))
            for s in scenarios
        ]
        scenario_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for i, res in enumerate(scenario_results):
            if isinstance(res, Exception):
                results.append({"scenario_id": scenarios[i].scenario_id, "error": str(res)})
                continue
            r: StressTestResult = res
            results.append({
                "scenario_id": r.scenario_id,
                "scenario_name": r.scenario_name,
                "loss_percentage": r.loss_percentage,
                "risk_level": r.risk_level,
                "breached_limits": r.breached_limits,
            })

        return {"total_scenarios": len(results), "results": results}

    # ---- Scenario Management ----

    def add_scenario(self, scenario: StressScenario) -> None:
        """Register a new stress scenario."""
        self._scenarios[scenario.scenario_id] = scenario

    def remove_scenario(self, scenario_id: str) -> None:
        """Remove a stress scenario."""
        self._scenarios.pop(scenario_id, None)

    def get_scenario(self, scenario_id: str) -> Optional[StressScenario]:
        """Get a scenario by ID."""
        return self._scenarios.get(scenario_id)

    def list_scenarios(self) -> list[StressScenario]:
        """List all registered scenarios."""
        return list(self._scenarios.values())

    # ---- Internal ----

    async def _run_single_scenario(
        self,
        scenario: StressScenario,
        positions: list[dict],
        total_value: float,
    ) -> StressTestResult:
        """Apply a single scenario to the portfolio and compute impact."""
        post_shock_value = total_value
        affected = 0
        breached_limits: list[str] = []

        for pos in positions:
            if not isinstance(pos, dict):
                continue
            symbol = pos.get("symbol", "")
            market_value = pos.get("market_value", 0.0)

            # Find applicable shock
            shock = self._find_shock(scenario.shocks, symbol, pos)
            if shock != 0.0:
                affected += 1
                post_shock_value -= market_value * abs(shock)

                # Check limits
                if abs(shock) > 0.20:
                    breached_limits.append(f"{symbol}: shock > 20%")

        absolute_loss = post_shock_value - total_value
        loss_pct = (absolute_loss / total_value * 100) if total_value > 0 else 0.0

        # Determine risk level
        risk_level = self._classify_risk_level(loss_pct)

        return StressTestResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            pre_shock_value=total_value,
            post_shock_value=post_shock_value,
            absolute_loss=absolute_loss,
            loss_percentage=loss_pct,
            positions_affected=affected,
            breached_limits=breached_limits,
            risk_level=risk_level,
        )

    @staticmethod
    def _find_shock(shocks: dict[str, float], symbol: str, position: dict) -> float:
        """Find the applicable shock for a position."""
        # Direct symbol match
        if symbol in shocks:
            return shocks[symbol]

        # Asset class match
        asset_class = position.get("asset_class", "").lower()
        for key, val in shocks.items():
            if key.lower() == asset_class:
                return val

        # Wildcard / broad market shock
        return shocks.get("*", 0.0)

    @staticmethod
    def _classify_risk_level(loss_pct: float) -> str:
        """Classify risk level based on loss percentage."""
        abs_loss = abs(loss_pct)
        if abs_loss > 30:
            return "critical"
        elif abs_loss > 15:
            return "high"
        elif abs_loss > 5:
            return "medium"
        return "low"

    async def _load_default_scenarios(self) -> None:
        """Load built-in stress testing scenarios."""
        defaults: list[tuple[str, str, str, dict[str, float]]] = [
            ("2008_financial_crisis", "2008 Financial Crisis", "Global financial crisis collapse",
             {"*": -0.40, "equity": -0.50, "real_estate": -0.60}),
            ("2020_covid_crash", "2020 COVID Crash", "Pandemic-driven market crash",
             {"*": -0.30, "equity": -0.35, "energy": -0.50, "travel": -0.60}),
            ("2022_inflation_shock", "2022 Inflation Shock", "Rate-hike driven selloff",
             {"*": -0.20, "equity": -0.25, "growth": -0.40, "bond": -0.15}),
            ("flash_crash", "Flash Crash", "Sudden intraday liquidity crisis",
             {"*": -0.10, "equity": -0.15}),
            ("interest_rate_spike", "Interest Rate Spike", "Sudden +200bp rate hike",
             {"bond": -0.15, "equity": -0.12, "real_estate": -0.20, "growth": -0.25}),
            ("liquidity_crisis", "Liquidity Crisis", "Market-wide liquidity freeze",
             {"*": -0.25, "small_cap": -0.40, "high_yield": -0.35}),
            ("currency_crisis", "Currency Crisis", "Major FX dislocation",
             {"forex": -0.20, "commodity": -0.15, "emerging_market": -0.30}),
            ("volatility_spike", "Volatility Spike", "VIX surges to 80+",
             {"equity": -0.22, "option": -0.35}),
            ("credit_crunch", "Credit Crunch", "Credit markets freeze",
             {"bond": -0.10, "corporate_bond": -0.20, "high_yield": -0.30, "equity": -0.15}),
            ("stagflation", "Stagflation", "Stagnation + inflation",
             {"equity": -0.20, "bond": -0.12, "commodity": 0.10, "gold": 0.25}),
        ]

        for sid, name, desc, shocks in defaults:
            scenario = StressScenario(
                scenario_id=sid,
                name=name,
                description=desc,
                category="historical" if "crisis" in sid or "crash" in sid else "macro",
                shocks=shocks,
            )
            self._scenarios[sid] = scenario

        logger.info(f"Loaded {len(defaults)} default stress scenarios.")
