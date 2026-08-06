"""Commit 11 Part 1.4: Institutional Portfolio Research Platform.

Portfolio construction, optimization, risk modeling, stress testing,
and scenario analysis for institutional-grade portfolio management.

Architecture::

    Alpha Pool → Portfolio Builder → Optimizer → Constraint Engine
    → Risk Model → Scenario Analysis → Portfolio Report
"""

from __future__ import annotations

# ── Core Engine ──────────────────────────────────────────────────────────────
from .portfolio_engine import PortfolioEngine, PortfolioEngineState
from .portfolio_manager import PortfolioManager, PortfolioManagerState
from .portfolio_runtime import PortfolioRuntime, PortfolioRuntimeState
from .portfolio_context import PortfolioContext
from .portfolio_registry import PortfolioRegistry
from .portfolio_repository import PortfolioRepository

# ── Construction ─────────────────────────────────────────────────────────────
from .portfolio_builder import PortfolioBuilder, BuildMethod
from .allocation_engine import AllocationEngine, AllocationMethod
from .rebalancer import Rebalancer, RebalanceMethod, RebalancePlan
from .turnover_optimizer import TurnoverOptimizer, TurnoverPlan
from .transaction_cost_optimizer import TransactionCostOptimizer

# ── Optimizers ───────────────────────────────────────────────────────────────
from .optimizer import Optimizer, OptimizerType, OptimizeResult
from .optimizer_factory import OptimizerFactory
from .mean_variance import MeanVarianceOptimizer
from .risk_parity import RiskParityOptimizer
from .black_litterman import BlackLittermanOptimizer, BLView
from .hierarchical_risk_parity import HRPOptimizer

# ── Risk Models ──────────────────────────────────────────────────────────────
from .constraint_engine import ConstraintEngine, Constraint, ConstraintType
from .factor_risk_model import FactorRiskModel, FactorRiskReport
from .covariance_estimator import CovarianceEstimator, CovarianceMethod
from .tracking_error import TrackingErrorModel, TrackingErrorReport
from .var_model import VaRModel, VaRMethod, VaRReport
from .cvar_model import CVaRModel, CVaRReport

# ── Stress Testing & Scenario ────────────────────────────────────────────────
from .stress_testing import StressTestEngine, StressScenario, StressTestReport
from .scenario_analysis import ScenarioAnalyzer, ScenarioType, ScenarioReport
from .exposure_analysis import ExposureAnalyzer, ExposureReport

# ── Analytics & Report ───────────────────────────────────────────────────────
from .attribution_engine import PortfolioAttribution, AttributionReport
from .portfolio_statistics import PortfolioStatistics, PortfolioStats
from .portfolio_report import PortfolioReportGenerator, PortfolioReportFormat
from .metrics import PortfolioMetrics
from .telemetry import PortfolioTracer, PortfolioSpan, PortfolioSpanContext
from .diagnostics import PortfolioDiagnostics, PortfolioDiagnosticReport, PortfolioDiagnosticStatus
from .health import PortfolioHealthCheck

__all__ = [
    # Core Engine
    "PortfolioEngine",
    "PortfolioEngineState",
    "PortfolioManager",
    "PortfolioManagerState",
    "PortfolioRuntime",
    "PortfolioRuntimeState",
    "PortfolioContext",
    "PortfolioRegistry",
    "PortfolioRepository",
    # Construction
    "PortfolioBuilder",
    "BuildMethod",
    "AllocationEngine",
    "AllocationMethod",
    "Rebalancer",
    "RebalanceMethod",
    "RebalancePlan",
    "TurnoverOptimizer",
    "TurnoverPlan",
    "TransactionCostOptimizer",
    # Optimizers
    "Optimizer",
    "OptimizerType",
    "OptimizeResult",
    "OptimizerFactory",
    "MeanVarianceOptimizer",
    "RiskParityOptimizer",
    "BlackLittermanOptimizer",
    "BLView",
    "HRPOptimizer",
    # Risk Models
    "ConstraintEngine",
    "Constraint",
    "ConstraintType",
    "FactorRiskModel",
    "FactorRiskReport",
    "CovarianceEstimator",
    "CovarianceMethod",
    "TrackingErrorModel",
    "TrackingErrorReport",
    "VaRModel",
    "VaRMethod",
    "VaRReport",
    "CVaRModel",
    "CVaRReport",
    # Stress Testing & Scenario
    "StressTestEngine",
    "StressScenario",
    "StressTestReport",
    "ScenarioAnalyzer",
    "ScenarioType",
    "ScenarioReport",
    "ExposureAnalyzer",
    "ExposureReport",
    # Analytics & Report
    "PortfolioAttribution",
    "AttributionReport",
    "PortfolioStatistics",
    "PortfolioStats",
    "PortfolioReportGenerator",
    "PortfolioReportFormat",
    "PortfolioMetrics",
    "PortfolioTracer",
    "PortfolioSpan",
    "PortfolioSpanContext",
    "PortfolioDiagnostics",
    "PortfolioDiagnosticReport",
    "PortfolioDiagnosticStatus",
    "PortfolioHealthCheck",
]
