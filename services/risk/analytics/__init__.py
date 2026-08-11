"""
Enterprise Risk Analytics Platform

A comprehensive platform for institutional risk analytics including:
- Stress Testing & Scenario Analysis
- Value-at-Risk (VaR) — Historical, Parametric, Monte Carlo
- Conditional VaR (Expected Shortfall)
- Monte Carlo Simulation
- Sensitivity Analysis
- Risk Attribution
- Factor Risk Decomposition
- Capital Adequacy Assessment
- Enterprise Risk Dashboard
- Automated Risk Reporting

Architecture::

    Market Data
        │
        ▼
    Portfolio Snapshot
        │
        ▼
    Enterprise Risk Analytics
        │
    ┌──────────┬───────────┬──────────┐
    │          │           │          │
    Stress     VaR/CVaR   MonteCarlo  Attribution
    │          │           │          │
    └──────────┴───────────┴──────────┘
        │
        ▼
    Risk Dashboard & Reports
"""

from .risk_analytics_engine import RiskAnalyticsEngine, AnalyticsConfig, AnalyticsResult
from .analytics_runtime import AnalyticsRuntime, AnalyticsRuntimeConfig, RuntimeStatus, RuntimeState
from .analytics_manager import AnalyticsManager
from .stress_testing_engine import StressTestingEngine, StressScenario, StressTestResult
from .stress_test_runner import StressTestRunner, StressTestRunConfig, StressTestRunResult
from .scenario_library import ScenarioLibrary, Scenario
from .scenario_repository import ScenarioRepository
from .scenario_builder import ScenarioBuilder
from .scenario_comparison import ScenarioComparison, ComparisonResult
from .historical_replay import HistoricalReplay, HistoricalPeriod, ReplayResult
from .shock_generator import ShockGenerator, ShockConfig, ShockVector
from .var_engine import VaREngine, VaRConfig, VaRResult
from .historical_var import HistoricalVaR
from .parametric_var import ParametricVaR
from .montecarlo_var import MonteCarloVaR
from .cvar_engine import CVaREngine
from .montecarlo_engine import MonteCarloEngine, MonteCarloConfig, MonteCarloResult
from .path_generator import PathGenerator, PathConfig
from .sensitivity_analysis import SensitivityAnalyzer
from .risk_attribution_engine import RiskAttributionEngine
from .factor_risk_decomposition import FactorRiskDecomposition, FactorExposure
from .capital_adequacy_engine import CapitalAdequacyEngine, CapitalAssessment
from .enterprise_risk_dashboard import EnterpriseRiskDashboard, DashboardSnapshot
from .automated_reporting import AutomatedReporting
from .report_scheduler import ReportScheduler, ReportSchedule, ScheduleType, ReportStatus
from .report_templates import ReportTemplates
from .metrics import AnalyticsMetrics, MetricsRegistry
from .telemetry import AnalyticsTelemetry, Span, Trace
from .diagnostics import AnalyticsDiagnostics, DiagnosticResult
from .health import AnalyticsHealth, HealthStatus, HealthProbeResult

__all__ = [
    # Core
    "RiskAnalyticsEngine",
    "AnalyticsConfig",
    "AnalyticsResult",
    "AnalyticsRuntime",
    "AnalyticsRuntimeConfig",
    "RuntimeStatus",
    "RuntimeState",
    "AnalyticsManager",
    # Stress Testing
    "StressTestingEngine",
    "StressScenario",
    "StressTestResult",
    "StressTestRunner",
    "StressTestRunConfig",
    "StressTestRunResult",
    # Scenarios
    "ScenarioLibrary",
    "Scenario",
    "ScenarioRepository",
    "ScenarioBuilder",
    "ScenarioComparison",
    "ComparisonResult",
    "HistoricalReplay",
    "HistoricalPeriod",
    "ReplayResult",
    "ShockGenerator",
    "ShockConfig",
    "ShockVector",
    # VaR
    "VaREngine",
    "VaRConfig",
    "VaRResult",
    "HistoricalVaR",
    "ParametricVaR",
    "MonteCarloVaR",
    # CVaR
    "CVaREngine",
    # Monte Carlo
    "MonteCarloEngine",
    "MonteCarloConfig",
    "MonteCarloResult",
    "PathGenerator",
    "PathConfig",
    # Sensitivity & Attribution
    "SensitivityAnalyzer",
    "RiskAttributionEngine",
    "FactorRiskDecomposition",
    "FactorExposure",
    # Capital
    "CapitalAdequacyEngine",
    "CapitalAssessment",
    # Dashboard & Reporting
    "EnterpriseRiskDashboard",
    "DashboardSnapshot",
    "AutomatedReporting",
    "ReportScheduler",
    "ReportSchedule",
    "ScheduleType",
    "ReportStatus",
    "ReportTemplates",
    # Observability
    "AnalyticsMetrics",
    "MetricsRegistry",
    "AnalyticsTelemetry",
    "Span",
    "Trace",
    "AnalyticsDiagnostics",
    "DiagnosticResult",
    "AnalyticsHealth",
    "HealthStatus",
    "HealthProbeResult",
]
