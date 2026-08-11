"""
Risk Analytics Engine — Unified entry point for all enterprise risk analytics.

Orchestrates the full analytics pipeline: stress testing, VaR computation,
Monte Carlo simulation, attribution, sensitivity, and factor decomposition.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsConfig:
    """Configuration for the risk analytics engine."""
    enable_stress_testing: bool = True
    enable_var: bool = True
    enable_cvar: bool = True
    enable_montecarlo: bool = True
    enable_attribution: bool = True
    enable_factor_decomposition: bool = True
    enable_sensitivity: bool = True
    enable_capital_assessment: bool = True
    parallel_execution: bool = True
    max_parallel_tasks: int = 8
    confidence_levels: list[float] = field(default_factory=lambda: [0.95, 0.99])
    time_horizons_days: list[int] = field(default_factory=lambda: [1, 5, 10, 20])
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsResult:
    """Result from a full analytics pipeline run."""
    analysis_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stress_tests: Optional[dict[str, Any]] = None
    var_results: Optional[dict[str, Any]] = None
    cvar_results: Optional[dict[str, Any]] = None
    montecarlo_results: Optional[dict[str, Any]] = None
    attribution: Optional[dict[str, Any]] = None
    factor_decomposition: Optional[dict[str, Any]] = None
    sensitivity: Optional[dict[str, Any]] = None
    capital_assessment: Optional[dict[str, Any]] = None
    analysis_time_ms: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskAnalyticsEngine:
    """
    Unified entry point for enterprise risk analytics.

    Orchestrates the complete analytics pipeline::

        Portfolio Data
            │
            ├── Stress Testing
            ├── VaR (Historical / Parametric / Monte Carlo)
            ├── CVaR (Expected Shortfall)
            ├── Monte Carlo Simulation
            ├── Sensitivity Analysis
            ├── Risk Attribution
            ├── Factor Risk Decomposition
            └── Capital Adequacy Assessment
                    │
                    ▼
            AnalyticsResult

    Usage::

        engine = RiskAnalyticsEngine(config=AnalyticsConfig())
        await engine.initialize()
        result = await engine.analyze(portfolio_data)
    """

    def __init__(self, config: Optional[AnalyticsConfig] = None) -> None:
        self._config = config or AnalyticsConfig()
        self._initialized = False
        self._sub_engines: dict[str, Any] = {}

    @property
    def config(self) -> AnalyticsConfig:
        return self._config

    async def initialize(self) -> None:
        """Initialize the analytics engine and register sub-engines."""
        if self._initialized:
            return
        logger.info("RiskAnalyticsEngine initializing...")

        # Sub-engines are injected or created by the AnalyticsManager.
        # The engine itself is a facade that coordinates pipeline execution.
        self._initialized = True
        logger.info("RiskAnalyticsEngine initialized.")

    async def analyze(self, portfolio_data: dict[str, Any]) -> AnalyticsResult:
        """
        Run the complete enterprise analytics pipeline.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio snapshot containing positions, balances, market data,
            and configuration for analysis.

        Returns
        -------
        AnalyticsResult
            Comprehensive analytics result.
        """
        import time
        import uuid

        analysis_id = str(uuid.uuid4())
        t_start = time.perf_counter()

        logger.info(f"RiskAnalyticsEngine: starting analysis {analysis_id[:8]}...")

        tasks = {}
        errors = []

        # Launch parallel sub-analyses
        if self._config.enable_stress_testing:
            tasks["stress_tests"] = asyncio.create_task(
                self._run_stress_tests(portfolio_data),
                name="stress_tests",
            )

        if self._config.enable_var:
            tasks["var_results"] = asyncio.create_task(
                self._run_var(portfolio_data),
                name="var",
            )

        if self._config.enable_cvar:
            tasks["cvar_results"] = asyncio.create_task(
                self._run_cvar(portfolio_data),
                name="cvar",
            )

        if self._config.enable_montecarlo:
            tasks["montecarlo_results"] = asyncio.create_task(
                self._run_montecarlo(portfolio_data),
                name="montecarlo",
            )

        if self._config.enable_attribution:
            tasks["attribution"] = asyncio.create_task(
                self._run_attribution(portfolio_data),
                name="attribution",
            )

        if self._config.enable_factor_decomposition:
            tasks["factor_decomposition"] = asyncio.create_task(
                self._run_factor_decomposition(portfolio_data),
                name="factor",
            )

        if self._config.enable_sensitivity:
            tasks["sensitivity"] = asyncio.create_task(
                self._run_sensitivity(portfolio_data),
                name="sensitivity",
            )

        if self._config.enable_capital_assessment:
            tasks["capital_assessment"] = asyncio.create_task(
                self._run_capital_assessment(portfolio_data),
                name="capital",
            )

        # Await all tasks
        results: dict[str, Any] = {}
        for key, task in tasks.items():
            try:
                results[key] = await task
            except Exception as e:
                logger.error(f"Analytics sub-task '{key}' failed: {e}")
                results[key] = None
                errors.append({"component": key, "error": str(e)})

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        result = AnalyticsResult(
            analysis_id=analysis_id,
            stress_tests=results.get("stress_tests"),
            var_results=results.get("var_results"),
            cvar_results=results.get("cvar_results"),
            montecarlo_results=results.get("montecarlo_results"),
            attribution=results.get("attribution"),
            factor_decomposition=results.get("factor_decomposition"),
            sensitivity=results.get("sensitivity"),
            capital_assessment=results.get("capital_assessment"),
            analysis_time_ms=elapsed_ms,
            errors=errors,
        )

        logger.info(
            f"RiskAnalyticsEngine: analysis {analysis_id[:8]} complete "
            f"in {elapsed_ms:.1f}ms with {len(errors)} errors."
        )
        return result

    # ---- Sub-analysis stubs (delegated to injected engines) ----

    async def _run_stress_tests(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to StressTestingEngine."""
        engine = self._sub_engines.get("stress")
        if engine:
            return await engine.run_stress_tests(portfolio_data)
        return {"status": "not_configured", "scenarios": 0}

    async def _run_var(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to VaREngine."""
        engine = self._sub_engines.get("var")
        if engine:
            return await engine.calculate_var(portfolio_data)
        return {"status": "not_configured"}

    async def _run_cvar(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to CVaREngine."""
        engine = self._sub_engines.get("cvar")
        if engine:
            return await engine.calculate_cvar(portfolio_data)
        return {"status": "not_configured"}

    async def _run_montecarlo(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to MonteCarloEngine."""
        engine = self._sub_engines.get("montecarlo")
        if engine:
            return await engine.run_simulation(portfolio_data)
        return {"status": "not_configured"}

    async def _run_attribution(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to RiskAttributionEngine."""
        engine = self._sub_engines.get("attribution")
        if engine:
            return await engine.attribute_risk(portfolio_data)
        return {"status": "not_configured"}

    async def _run_factor_decomposition(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to FactorRiskDecomposition."""
        engine = self._sub_engines.get("factor")
        if engine:
            return await engine.decompose(portfolio_data)
        return {"status": "not_configured"}

    async def _run_sensitivity(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to SensitivityAnalyzer."""
        engine = self._sub_engines.get("sensitivity")
        if engine:
            return await engine.analyze(portfolio_data)
        return {"status": "not_configured"}

    async def _run_capital_assessment(self, portfolio_data: dict[str, Any]) -> dict[str, Any]:
        """Delegate to CapitalAdequacyEngine."""
        engine = self._sub_engines.get("capital")
        if engine:
            return await engine.assess(portfolio_data)
        return {"status": "not_configured"}

    # ---- Injectors ----

    def inject_sub_engine(self, name: str, engine: Any) -> None:
        """Inject a sub-engine for delegation."""
        self._sub_engines[name] = engine
