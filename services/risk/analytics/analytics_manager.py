"""
Analytics Manager — Top-level orchestrator for the enterprise risk analytics platform.

Coordinates all analytics subsystems (stress testing, VaR, scenario analysis,
attribution, capital assessment, reporting) and provides the unified external API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .analytics_runtime import AnalyticsRuntime, AnalyticsRuntimeConfig
from .risk_analytics_engine import RiskAnalyticsEngine
from .stress_testing_engine import StressTestingEngine
from .scenario_repository import ScenarioRepository
from .var_engine import VaREngine
from .cvar_engine import CVaREngine
from .montecarlo_engine import MonteCarloEngine
from .risk_attribution_engine import RiskAttributionEngine
from .capital_adequacy_engine import CapitalAdequacyEngine
from .enterprise_risk_dashboard import EnterpriseRiskDashboard
from .automated_reporting import AutomatedReporting
from .report_scheduler import ReportScheduler
from .sensitivity_analysis import SensitivityAnalyzer
from .factor_risk_decomposition import FactorRiskDecomposition

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """
    Top-level orchestrator for the enterprise risk analytics platform.

    Coordinates all analytics subsystems and provides a unified API
    for stress testing, VaR computation, scenario analysis, risk
    attribution, capital assessment, and automated reporting.

    Architecture::

        AnalyticsManager
            ├── RiskAnalyticsEngine
            ├── StressTestingEngine
            ├── VaREngine
            ├── CVaREngine
            ├── MonteCarloEngine
            ├── RiskAttributionEngine
            ├── FactorRiskDecomposition
            ├── SensitivityAnalyzer
            ├── CapitalAdequacyEngine
            ├── ScenarioRepository
            ├── EnterpriseRiskDashboard
            ├── AutomatedReporting
            ├── ReportScheduler
            └── AnalyticsRuntime

    Usage::

        mgr = AnalyticsManager()
        await mgr.initialize()
        await mgr.start()

        result = await mgr.analyze(portfolio_snapshot)
        await mgr.stop()
    """

    def __init__(
        self,
        analytics_engine: Optional[RiskAnalyticsEngine] = None,
        stress_engine: Optional[StressTestingEngine] = None,
        var_engine: Optional[VaREngine] = None,
        cvar_engine: Optional[CVaREngine] = None,
        mc_engine: Optional[MonteCarloEngine] = None,
        attribution_engine: Optional[RiskAttributionEngine] = None,
        factor_decomp: Optional[FactorRiskDecomposition] = None,
        sensitivity: Optional[SensitivityAnalyzer] = None,
        capital_engine: Optional[CapitalAdequacyEngine] = None,
        scenario_repo: Optional[ScenarioRepository] = None,
        dashboard: Optional[EnterpriseRiskDashboard] = None,
        reporting: Optional[AutomatedReporting] = None,
        scheduler: Optional[ReportScheduler] = None,
        runtime: Optional[AnalyticsRuntime] = None,
    ) -> None:
        self._analytics_engine = analytics_engine or RiskAnalyticsEngine()
        self._stress_engine = stress_engine or StressTestingEngine()
        self._var_engine = var_engine or VaREngine()
        self._cvar_engine = cvar_engine or CVaREngine()
        self._mc_engine = mc_engine or MonteCarloEngine()
        self._attribution_engine = attribution_engine or RiskAttributionEngine()
        self._factor_decomp = factor_decomp or FactorRiskDecomposition()
        self._sensitivity = sensitivity or SensitivityAnalyzer()
        self._capital_engine = capital_engine or CapitalAdequacyEngine()
        self._scenario_repo = scenario_repo or ScenarioRepository()
        self._dashboard = dashboard or EnterpriseRiskDashboard()
        self._reporting = reporting or AutomatedReporting()
        self._scheduler = scheduler or ReportScheduler()
        self._runtime = runtime or AnalyticsRuntime()
        self._initialized = False
        self._lock = asyncio.Lock()

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize all analytics subsystems."""
        if self._initialized:
            return
        logger.info("AnalyticsManager initializing all subsystems...")

        await asyncio.gather(
            self._runtime.initialize(),
            self._analytics_engine.initialize(),
            self._stress_engine.initialize(),
            self._var_engine.initialize(),
            self._cvar_engine.initialize(),
            self._mc_engine.initialize(),
            self._attribution_engine.initialize(),
            self._factor_decomp.initialize(),
            self._sensitivity.initialize(),
            self._capital_engine.initialize(),
            self._scenario_repo.initialize(),
            self._dashboard.initialize(),
            self._reporting.initialize(),
            self._scheduler.initialize(),
        )

        self._initialized = True
        logger.info("AnalyticsManager initialized.")

    async def start(self) -> None:
        """Start the analytics platform."""
        if not self._initialized:
            await self.initialize()
        await self._runtime.start()
        await self._scheduler.start()
        logger.info("AnalyticsManager started.")

    async def stop(self) -> None:
        """Stop the analytics platform."""
        await self._scheduler.stop()
        await self._runtime.stop()
        self._initialized = False
        logger.info("AnalyticsManager stopped.")

    # ---- Core API ----

    async def analyze(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """
        Full enterprise risk analytics pipeline.

        Pipeline: Portfolio → Stress Tests → VaR/CVaR → Monte Carlo
                  → Attribution → Factor Decomp → Sensitivity
                  → Capital Assessment → Report

        Returns a comprehensive analytics result.
        """
        if not self._initialized:
            await self.initialize()

        import time
        t_start = time.perf_counter()

        # Run analytics in parallel where possible
        stress_task = asyncio.create_task(self._stress_engine.run_stress_tests(portfolio_data))
        var_task = asyncio.create_task(self._var_engine.calculate_var(portfolio_data))
        cvar_task = asyncio.create_task(self._cvar_engine.calculate_cvar(portfolio_data))
        mc_task = asyncio.create_task(self._mc_engine.run_simulation(portfolio_data))
        attribution_task = asyncio.create_task(self._attribution_engine.attribute_risk(portfolio_data))
        factor_task = asyncio.create_task(self._factor_decomp.decompose(portfolio_data))
        sensitivity_task = asyncio.create_task(self._sensitivity.analyze(portfolio_data))
        capital_task = asyncio.create_task(self._capital_engine.assess(portfolio_data))

        results = await asyncio.gather(
            stress_task, var_task, cvar_task, mc_task,
            attribution_task, factor_task, sensitivity_task, capital_task,
            return_exceptions=True,
        )

        (stress_result, var_result, cvar_result, mc_result,
         attr_result, factor_result, sens_result, capital_result) = results

        # Build comprehensive result
        analysis_time_ms = (time.perf_counter() - t_start) * 1000

        result = {
            "stress_testing": stress_result if not isinstance(stress_result, Exception) else {"error": str(stress_result)},
            "var": var_result if not isinstance(var_result, Exception) else {"error": str(var_result)},
            "cvar": cvar_result if not isinstance(cvar_result, Exception) else {"error": str(cvar_result)},
            "monte_carlo": mc_result if not isinstance(mc_result, Exception) else {"error": str(mc_result)},
            "attribution": attr_result if not isinstance(attr_result, Exception) else {"error": str(attr_result)},
            "factor_decomposition": factor_result if not isinstance(factor_result, Exception) else {"error": str(factor_result)},
            "sensitivity": sens_result if not isinstance(sens_result, Exception) else {"error": str(sens_result)},
            "capital_adequacy": capital_result if not isinstance(capital_result, Exception) else {"error": str(capital_result)},
            "analysis_time_ms": analysis_time_ms,
        }

        # Update dashboard
        await self._dashboard.update(result)

        logger.info(
            f"Analytics pipeline complete: stress={bool(stress_result)}, "
            f"VaR={bool(var_result)}, CVaR={bool(cvar_result)}, "
            f"time={analysis_time_ms:.1f}ms"
        )
        return result

    async def stress_test(self, portfolio_data: dict[str, Any], scenario_ids: Optional[list[str]] = None) -> dict[str, Any]:
        """Run stress tests against specific scenarios."""
        if not self._initialized:
            await self.initialize()

        if scenario_ids:
            scenarios = await self._scenario_repo.get_by_ids(scenario_ids)
        else:
            scenarios = await self._scenario_repo.get_all()

        return await self._stress_engine.run_custom_stress_tests(portfolio_data, scenarios)

    async def calculate_var(self, portfolio_data: dict[str, Any], method: str = "all") -> dict[str, Any]:
        """Calculate VaR using specified method(s)."""
        if not self._initialized:
            await self.initialize()
        return await self._var_engine.calculate_var(portfolio_data, method=method)

    async def generate_report(self, portfolio_data: dict[str, Any], report_type: str = "daily") -> dict[str, Any]:
        """Generate an automated risk report."""
        if not self._initialized:
            await self.initialize()
        return await self._reporting.generate_report(portfolio_data, report_type=report_type)

    # ---- Query ----

    async def get_dashboard(self) -> dict[str, Any]:
        """Get enterprise risk dashboard data."""
        return await self._dashboard.get_snapshot()

    async def get_health(self) -> dict[str, Any]:
        """Get platform-wide health."""
        return await self._runtime.health_check()

    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        state = self._runtime.get_state()
        return {
            "runtime": {
                "status": state.status.value,
                "analyses_completed": state.analyses_completed,
                "analyses_failed": state.analyses_failed,
                "stress_tests_run": state.stress_tests_run,
                "var_calculations": state.var_calculations,
                "scenarios_run": state.scenarios_run,
                "reports_generated": state.reports_generated,
                "uptime_seconds": state.uptime_seconds,
            },
            "scenarios": await self._scenario_repo.count(),
            "scheduled_reports": await self._scheduler.get_schedule(),
        }

    # ---- Control ----

    async def pause_all(self) -> None:
        """Pause all analytics operations."""
        await self._runtime.pause()
        await self._scheduler.pause()
        logger.warning("AnalyticsManager: all operations paused.")

    async def resume_all(self) -> None:
        """Resume all analytics operations."""
        await self._runtime.resume()
        await self._scheduler.resume()
        logger.info("AnalyticsManager: all operations resumed.")
