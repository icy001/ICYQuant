"""
Portfolio & Intraday Risk Package — Real-time portfolio risk management.

Provides continuous portfolio monitoring, real-time PnL, exposure
tracking, risk alerts, and automated risk actions for production
portfolio risk management.

Architecture::

    Market Data → Portfolio Risk Engine
        ├── Real-Time PnL Engine
        ├── Real-Time Exposure Engine
        ├── Real-Time Margin Monitor
        ├── Intraday Risk Engine
        ├── Position Monitor
        ├── Drawdown Monitor
        ├── Concentration Risk Engine
        ├── Greeks Risk Engine
        ├── Factor Exposure Engine
        ├── Liquidity Risk Monitor
        ├── Correlation Monitor
        ├── Risk Alert Center → Alert Dispatcher
        ├── Risk Action Engine
        ├── Auto Hedging Policy
        ├── Strategy Pause Controller
        └── Kill Switch Controller
"""

# ---- Core Models ----
from .portfolio_snapshot import (
    PortfolioSnapshot,
    PositionSnapshot,
)
from .portfolio_health import (
    PortfolioHealthMonitor,
    PortfolioHealthStatus,
    PortfolioHealthReport,
    SubsystemHealth,
    SubsystemReport,
)

# ---- Portfolio Risk Engine ----
from .portfolio_risk_engine import (
    PortfolioRiskEngine,
    PortfolioRiskAssessment,
    AssessmentLevel,
)

# ---- Portfolio Runtime & Manager ----
from .portfolio_runtime import (
    PortfolioRuntime,
    PortfolioRuntimeConfig,
    RuntimeState as PortfolioRuntimeState,
    RuntimeStatus as PortfolioRuntimeStatus,
)
from .portfolio_manager import PortfolioManager
from .portfolio_monitor import (
    PortfolioMonitor,
    MonitorConfig,
    MonitorResult,
    MonitorStatus,
    PortfolioRiskLevel,
)

# ---- Real-Time Engines ----
from .realtime_pnl_engine import (
    RealtimePnLEngine,
    PnLSnapshot,
    PortfolioPnL,
)
from .realtime_exposure_engine import (
    RealtimeExposureEngine,
    ExposureSnapshot,
)
from .realtime_margin_monitor import (
    RealtimeMarginMonitor,
    MarginStatus,
)

# ---- Intraday Risk ----
from .intraday_risk_engine import (
    IntradayRiskEngine,
    IntradayRiskAssessment,
    IntradayRiskLevel,
)

# ---- Monitors ----
from .position_monitor import (
    PositionMonitor,
    PositionInfo,
    PositionAlert,
)
from .drawdown_monitor import (
    DrawdownMonitor,
    DrawdownEvent,
    DrawdownPeriod,
    DrawdownSeverity,
)
from .concentration_risk_engine import (
    ConcentrationRiskEngine,
    ConcentrationMetrics,
)
from .greeks_risk_engine import (
    GreeksRiskEngine,
    GreeksSnapshot,
)
from .factor_exposure_engine import (
    FactorExposureEngine,
    FactorExposure,
    FactorExposureReport,
    STANDARD_FACTORS,
)
from .liquidity_risk_monitor import (
    LiquidityRiskMonitor,
    LiquidityInfo,
    PortfolioLiquidityReport,
)
from .correlation_monitor import (
    CorrelationMonitor,
    CorrelationReport,
)

# ---- Alert System ----
from .risk_alert_center import (
    RiskAlertCenter,
    RiskAlert,
    AlertSeverity,
    AlertStatus,
)
from .alert_dispatcher import (
    AlertDispatcher,
    ChannelType,
    DispatchStatus,
    DispatchRecord,
    ChannelConfig,
)

# ---- Risk Actions ----
from .risk_action_engine import (
    RiskActionEngine,
    RiskAction,
    ActionType,
    ActionStatus,
    ActionMode,
)
from .auto_hedging_policy import (
    AutoHedgingPolicy,
    HedgingRule,
    HedgeType,
    HedgeTrigger,
    HedgeSignal,
)
from .strategy_pause_controller import (
    StrategyPauseController,
    StrategyState,
    AutoPauseRule,
    PauseReason,
    PauseStatus,
)
from .kill_switch_controller import (
    KillSwitchController,
    KillSwitchEvent,
    KillSwitchRule,
    KillSwitchStatus,
    KillTrigger,
)

# ---- Observability ----
from .metrics import PortfolioMetrics
from .telemetry import (
    PortfolioTelemetry,
    TelemetryPhase,
    TelemetrySpan,
    TelemetryTrace,
)
from .diagnostics import (
    PortfolioDiagnostics,
    DiagnosticStatus,
    DiagnosticCheck,
    DiagnosticReport,
)
from .health import (
    PortfolioHealthChecker,
    HealthStatus,
    ProbeType,
    ComponentHealth,
)

__all__ = [
    # ---- Core Models ----
    "PortfolioSnapshot",
    "PositionSnapshot",
    "PortfolioHealthMonitor",
    "PortfolioHealthStatus",
    "PortfolioHealthReport",
    "SubsystemHealth",
    "SubsystemReport",
    # ---- Portfolio Risk Engine ----
    "PortfolioRiskEngine",
    "PortfolioRiskAssessment",
    "AssessmentLevel",
    # ---- Runtime & Manager ----
    "PortfolioRuntime",
    "PortfolioRuntimeConfig",
    "PortfolioRuntimeState",
    "PortfolioRuntimeStatus",
    "PortfolioManager",
    "PortfolioMonitor",
    "MonitorConfig",
    "MonitorResult",
    "MonitorStatus",
    "PortfolioRiskLevel",
    # ---- Real-Time Engines ----
    "RealtimePnLEngine",
    "PnLSnapshot",
    "PortfolioPnL",
    "RealtimeExposureEngine",
    "ExposureSnapshot",
    "RealtimeMarginMonitor",
    "MarginStatus",
    # ---- Intraday Risk ----
    "IntradayRiskEngine",
    "IntradayRiskAssessment",
    "IntradayRiskLevel",
    # ---- Monitors ----
    "PositionMonitor",
    "PositionInfo",
    "PositionAlert",
    "DrawdownMonitor",
    "DrawdownEvent",
    "DrawdownPeriod",
    "DrawdownSeverity",
    "ConcentrationRiskEngine",
    "ConcentrationMetrics",
    "GreeksRiskEngine",
    "GreeksSnapshot",
    "FactorExposureEngine",
    "FactorExposure",
    "FactorExposureReport",
    "STANDARD_FACTORS",
    "LiquidityRiskMonitor",
    "LiquidityInfo",
    "PortfolioLiquidityReport",
    "CorrelationMonitor",
    "CorrelationReport",
    # ---- Alert System ----
    "RiskAlertCenter",
    "RiskAlert",
    "AlertSeverity",
    "AlertStatus",
    "AlertDispatcher",
    "ChannelType",
    "DispatchStatus",
    "DispatchRecord",
    "ChannelConfig",
    # ---- Risk Actions ----
    "RiskActionEngine",
    "RiskAction",
    "ActionType",
    "ActionStatus",
    "ActionMode",
    "AutoHedgingPolicy",
    "HedgingRule",
    "HedgeType",
    "HedgeTrigger",
    "HedgeSignal",
    "StrategyPauseController",
    "StrategyState",
    "AutoPauseRule",
    "PauseReason",
    "PauseStatus",
    "KillSwitchController",
    "KillSwitchEvent",
    "KillSwitchRule",
    "KillSwitchStatus",
    "KillTrigger",
    # ---- Observability ----
    "PortfolioMetrics",
    "PortfolioTelemetry",
    "TelemetryPhase",
    "TelemetrySpan",
    "TelemetryTrace",
    "PortfolioDiagnostics",
    "DiagnosticStatus",
    "DiagnosticCheck",
    "DiagnosticReport",
    "PortfolioHealthChecker",
    "HealthStatus",
    "ProbeType",
    "ComponentHealth",
]
