"""
Pre-Trade Risk Package — Production pre-trade risk engine.

All order intents must pass through this package before reaching OMS.
Provides a pluggable rule chain with 14 built-in checkers, approval
workflow, and full observability.

Architecture::

    Order Intent → PreTradeRiskEngine → Rule Chain (14 checkers)
        → Risk Decision → Approval Workflow → OMS
"""

from .risk_request import (
    RiskRequest,
    OrderSide,
    OrderType,
    InstrumentType,
)
from .risk_decision import (
    RiskDecision,
    Decision,
    RiskLevel,
)
from .risk_reason import (
    RiskReason,
    ReasonSeverity,
    ReasonCategory,
)
from .pre_trade_context import PreTradeContext
from .approval_policy import (
    ApprovalPolicy,
    ApprovalMode,
    ApprovalAction,
)
from .approval_workflow import (
    ApprovalWorkflow,
    ApprovalStatus,
    ApprovalRequest,
)
from .risk_rule_chain import RiskRuleChain
from .rule_executor import (
    RuleExecutor,
    RuleResult,
    RuleExecutionResult,
)
from .pre_trade_engine import PreTradeRiskEngine
from .pre_trade_runtime import (
    PreTradeRuntime,
    RuntimeStatus,
    RuntimeConfig,
    RuntimeState,
)
from .pre_trade_manager import PreTradeManager

# ---- Checkers ----
from .position_limit_checker import PositionLimitChecker
from .exposure_limit_checker import ExposureLimitChecker
from .leverage_checker import LeverageChecker
from .buying_power_checker import BuyingPowerChecker
from .cash_checker import CashChecker
from .margin_checker import MarginChecker
from .concentration_checker import ConcentrationChecker
from .liquidity_checker import LiquidityChecker
from .volatility_checker import VolatilityChecker
from .instrument_permission_checker import InstrumentPermissionChecker
from .compliance_checker import ComplianceChecker
from .order_size_validator import OrderSizeValidator
from .order_rate_limiter import OrderRateLimiter
from .trading_session_checker import TradingSessionChecker
from .market_status_checker import MarketStatusChecker

# ---- Observability ----
from .diagnostics import (
    PreTradeDiagnostics,
    DiagnosticStatus,
    DiagnosticCheck,
    DiagnosticReport,
)
from .metrics import PreTradeMetrics
from .telemetry import (
    PreTradeTelemetry,
    TelemetryPhase,
    TelemetrySpan,
    TelemetryTrace,
)
from .health import (
    PreTradeHealthChecker,
    HealthStatus,
    ProbeType,
    ComponentHealth,
    PreTradeHealthReport,
)

__all__ = [
    # ---- Core Models ----
    "RiskRequest",
    "OrderSide",
    "OrderType",
    "InstrumentType",
    "RiskDecision",
    "Decision",
    "RiskLevel",
    "RiskReason",
    "ReasonSeverity",
    "ReasonCategory",
    "PreTradeContext",
    # ---- Approval ----
    "ApprovalPolicy",
    "ApprovalMode",
    "ApprovalAction",
    "ApprovalWorkflow",
    "ApprovalStatus",
    "ApprovalRequest",
    # ---- Rule Engine ----
    "RiskRuleChain",
    "RuleExecutor",
    "RuleResult",
    "RuleExecutionResult",
    # ---- Core Engine ----
    "PreTradeRiskEngine",
    "PreTradeRuntime",
    "RuntimeStatus",
    "RuntimeConfig",
    "RuntimeState",
    "PreTradeManager",
    # ---- Checkers ----
    "PositionLimitChecker",
    "ExposureLimitChecker",
    "LeverageChecker",
    "BuyingPowerChecker",
    "CashChecker",
    "MarginChecker",
    "ConcentrationChecker",
    "LiquidityChecker",
    "VolatilityChecker",
    "InstrumentPermissionChecker",
    "ComplianceChecker",
    "OrderSizeValidator",
    "OrderRateLimiter",
    "TradingSessionChecker",
    "MarketStatusChecker",
    # ---- Observability ----
    "PreTradeDiagnostics",
    "DiagnosticStatus",
    "DiagnosticCheck",
    "DiagnosticReport",
    "PreTradeMetrics",
    "PreTradeTelemetry",
    "TelemetryPhase",
    "TelemetrySpan",
    "TelemetryTrace",
    "PreTradeHealthChecker",
    "HealthStatus",
    "ProbeType",
    "ComponentHealth",
    "PreTradeHealthReport",
]
