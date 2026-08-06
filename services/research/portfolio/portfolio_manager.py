"""Portfolio Manager — lifecycle coordinator for all portfolio research subsystems.

Coordinates portfolio construction, optimization, risk modeling,
stress testing, and reporting through a unified interface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .portfolio_context import PortfolioContext
from .portfolio_registry import PortfolioRegistry
from .portfolio_repository import PortfolioRepository
from .portfolio_builder import PortfolioBuilder, BuildMethod
from .optimizer_factory import OptimizerFactory
from .constraint_engine import ConstraintEngine
from .allocation_engine import AllocationEngine
from .rebalancer import Rebalancer
from .factor_risk_model import FactorRiskModel
from .covariance_estimator import CovarianceEstimator
from .tracking_error import TrackingErrorModel
from .var_model import VaRModel
from .cvar_model import CVaRModel
from .stress_testing import StressTestEngine
from .scenario_analysis import ScenarioAnalyzer
from .exposure_analysis import ExposureAnalyzer
from .attribution_engine import PortfolioAttribution
from .portfolio_statistics import PortfolioStatistics
from .portfolio_report import PortfolioReportGenerator

logger = logging.getLogger(__name__)


class PortfolioManagerState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class PortfolioManager:
    """Lifecycle coordinator for all portfolio research subsystems.

    Responsibilities:
    * Bootstrap portfolio builder, optimizer factory, risk models
    * Orchestrate portfolio construction and optimization
    * Coordinate risk analysis, stress testing, and attribution
    * Generate comprehensive portfolio reports
    """

    def __init__(
        self,
        ctx: PortfolioContext,
        registry: PortfolioRegistry,
        repository: PortfolioRepository,
    ) -> None:
        self._ctx = ctx
        self._registry = registry
        self._repository = repository
        self._state = PortfolioManagerState.UNINITIALIZED

        # Subsystems (initialized during boot)
        self._builder: Optional[PortfolioBuilder] = None
        self._optimizer_factory: Optional[OptimizerFactory] = None
        self._constraint_engine: Optional[ConstraintEngine] = None
        self._allocation_engine: Optional[AllocationEngine] = None
        self._rebalancer: Optional[Rebalancer] = None
        self._factor_risk: Optional[FactorRiskModel] = None
        self._cov_estimator: Optional[CovarianceEstimator] = None
        self._tracking_error: Optional[TrackingErrorModel] = None
        self._var_model: Optional[VaRModel] = None
        self._cvar_model: Optional[CVaRModel] = None
        self._stress_engine: Optional[StressTestEngine] = None
        self._scenario_analyzer: Optional[ScenarioAnalyzer] = None
        self._exposure_analyzer: Optional[ExposureAnalyzer] = None
        self._attribution: Optional[PortfolioAttribution] = None
        self._statistics: Optional[PortfolioStatistics] = None
        self._report_generator: Optional[PortfolioReportGenerator] = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._state = PortfolioManagerState.INITIALIZING

        # Construction
        self._builder = PortfolioBuilder()
        self._allocation_engine = AllocationEngine()
        self._rebalancer = Rebalancer()

        # Optimization
        self._optimizer_factory = OptimizerFactory()
        self._constraint_engine = ConstraintEngine()

        # Risk models
        self._cov_estimator = CovarianceEstimator()
        self._factor_risk = FactorRiskModel(self._cov_estimator)
        self._tracking_error = TrackingErrorModel()
        self._var_model = VaRModel()
        self._cvar_model = CVaRModel()

        # Stress & Scenario
        self._stress_engine = StressTestEngine()
        self._scenario_analyzer = ScenarioAnalyzer()
        self._exposure_analyzer = ExposureAnalyzer()

        # Analytics
        self._attribution = PortfolioAttribution()
        self._statistics = PortfolioStatistics()
        self._report_generator = PortfolioReportGenerator()

        self._state = PortfolioManagerState.READY
        logger.info("PortfolioManager initialized")

    async def shutdown(self) -> None:
        self._state = PortfolioManagerState.SHUTTING_DOWN
        self._state = PortfolioManagerState.TERMINATED
        logger.info("PortfolioManager shutdown complete")

    # ── construct ──────────────────────────────────────────────────────────

    async def construct_portfolio(
        self,
        alpha_pool: List[str],
        universe: List[str],
        method: str = "equal_weight",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Construct a portfolio from alpha pool signals."""
        self._ensure_ready()
        self._state = PortfolioManagerState.RUNNING
        try:
            assert self._builder is not None
            assert self._allocation_engine is not None

            # Build candidate universe from alpha pool
            candidates = await self._builder.build(
                alpha_pool=alpha_pool,
                universe=universe,
                method=BuildMethod(method),
                **kwargs,
            )

            # Apply initial allocation
            portfolio = await self._allocation_engine.allocate(
                candidates=candidates,
                method=method,
            )

            # Save to repository
            saved = await self._repository.create_portfolio({
                "name": f"portfolio_{self._ctx.session_id[:8]}",
                "universe": universe,
                "weights": portfolio.get("weights", {}),
                "tags": self._ctx.tags,
            })

            return {"portfolio": saved, "candidates": candidates, **portfolio}
        finally:
            self._state = PortfolioManagerState.READY

    # ── optimize ───────────────────────────────────────────────────────────

    async def optimize_portfolio(
        self,
        portfolio: Dict[str, Any],
        optimizer_type: str = "mean_variance",
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Optimize portfolio weights with constraints."""
        self._ensure_ready()
        self._state = PortfolioManagerState.RUNNING
        try:
            assert self._optimizer_factory is not None
            assert self._constraint_engine is not None
            assert self._cov_estimator is not None

            # Estimate covariance
            universe = portfolio.get("universe", [])
            cov_matrix = await self._cov_estimator.estimate(
                universe=universe,
                method=self._ctx.covariance_method,
            )

            # Build constraints
            if constraints is None:
                constraints = self._build_default_constraints(universe)

            constraint_set = self._constraint_engine.build(constraints)

            # Create and run optimizer
            optimizer = self._optimizer_factory.create(
                optimizer_type,
                cov_matrix=cov_matrix,
                constraints=constraint_set,
                risk_aversion=self._ctx.risk_aversion,
                **kwargs,
            )

            result = await optimizer.optimize()

            # Update portfolio weights
            portfolio["weights"] = result.weights
            portfolio["optimizer"] = optimizer_type
            portfolio["status"] = "optimized"

            # Save weights and optimization
            await self._repository.save_weights(
                portfolio["id"], result.weights
            )
            await self._repository.save_optimization(
                portfolio["id"], result.to_dict()
            )

            return {
                "portfolio": portfolio,
                "optimization": result.to_dict(),
            }
        finally:
            self._state = PortfolioManagerState.READY

    # ── analyze ────────────────────────────────────────────────────────────

    async def analyze_portfolio(
        self,
        portfolio: Dict[str, Any],
        include_risk: bool = True,
        include_attribution: bool = True,
        include_stress: bool = True,
        include_scenario: bool = True,
    ) -> Dict[str, Any]:
        """Comprehensive portfolio analysis."""
        self._ensure_ready()
        self._state = PortfolioManagerState.RUNNING
        try:
            weights = portfolio.get("weights", {})
            universe = portfolio.get("universe", [])
            results: Dict[str, Any] = {"portfolio_id": portfolio["id"]}

            # Statistics
            assert self._statistics is not None
            stats = await self._statistics.compute(weights=weights, universe=universe)
            results["statistics"] = stats.to_dict()

            # Risk analysis
            if include_risk:
                results["risk"] = await self._analyze_risk(weights, universe)

            # Attribution
            if include_attribution:
                assert self._attribution is not None
                attr = await self._attribution.analyze(
                    weights=weights,
                    benchmark=self._ctx.benchmark,
                )
                results["attribution"] = attr.to_dict()

            # Stress testing
            if include_stress:
                assert self._stress_engine is not None
                stress = await self._stress_engine.run(weights=weights)
                results["stress_test"] = stress.to_dict()

            # Scenario analysis
            if include_scenario:
                assert self._scenario_analyzer is not None
                scenarios = await self._scenario_analyzer.analyze(
                    weights=weights, universe=universe
                )
                results["scenarios"] = scenarios.to_dict()

            # Generate report
            assert self._report_generator is not None
            report = await self._report_generator.generate(
                portfolio=portfolio,
                analysis=results,
            )
            results["report"] = report

            return results
        finally:
            self._state = PortfolioManagerState.READY

    # ── helpers ────────────────────────────────────────────────────────────

    async def _analyze_risk(
        self, weights: Dict[str, float], universe: List[str]
    ) -> Dict[str, Any]:
        risk_results: Dict[str, Any] = {}

        # Factor risk
        assert self._factor_risk is not None
        risk_results["factor_risk"] = (
            await self._factor_risk.analyze(weights=weights)
        ).to_dict()

        # Tracking error
        assert self._tracking_error is not None
        risk_results["tracking_error"] = (
            await self._tracking_error.compute(
                weights=weights, benchmark=self._ctx.benchmark
            )
        ).to_dict()

        # VaR
        assert self._var_model is not None
        risk_results["var"] = (
            await self._var_model.compute(
                weights=weights,
                confidence=self._ctx.var_confidence,
                method=self._ctx.var_method,
            )
        ).to_dict()

        # CVaR
        assert self._cvar_model is not None
        risk_results["cvar"] = (
            await self._cvar_model.compute(
                weights=weights,
                confidence=self._ctx.var_confidence,
            )
        ).to_dict()

        # Exposure
        assert self._exposure_analyzer is not None
        risk_results["exposure"] = (
            await self._exposure_analyzer.analyze(weights=weights)
        ).to_dict()

        return risk_results

    def _build_default_constraints(
        self, universe: List[str]
    ) -> Dict[str, Any]:
        return {
            "long_only": self._ctx.long_only,
            "fully_invested": self._ctx.fully_invested,
            "min_weight": self._ctx.min_weight,
            "max_weight": self._ctx.max_weight,
            "max_leverage": self._ctx.max_leverage,
            "max_turnover": self._ctx.max_turnover,
            "sector_limits": self._ctx.sector_constraints,
            "num_assets": len(universe),
        }

    def _ensure_ready(self) -> None:
        if self._state != PortfolioManagerState.READY:
            raise RuntimeError(
                f"PortfolioManager is {self._state.value}, expected ready"
            )

    @property
    def state(self) -> PortfolioManagerState:
        return self._state
