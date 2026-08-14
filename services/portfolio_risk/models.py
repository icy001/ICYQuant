"""Portfolio risk domain models (Commit 36).

Establishes the four core concepts of the portfolio risk domain:

.. code-block:: text

    Exposure -> Leverage -> Risk Snapshot -> Risk Assessment

``PortfolioExposure`` is the per-instrument position; ``PortfolioRiskSnapshot``
captures gross / net exposure and leverage at a point in time;
``PortfolioRiskLimit`` defines the risk boundaries; ``PortfolioRiskAssessment``
combines the snapshot with the limit violations.

The concentration models (``PositionConcentration``, ``ConcentrationMetric``
and ``ConcentrationRiskLevel``) answer whether the portfolio's risk is overly
concentrated in a few positions, sectors, asset classes or countries.

The factor models (``FactorExposure``, ``PositionFactorExposure``,
``FactorRiskContribution`` and ``PortfolioFactorRiskSnapshot``) express the
portfolio in factor space and attribute total factor risk to each factor.

The VaR / Expected Shortfall models (``VaRResult``,
``ExpectedShortfallResult`` and ``TailRiskSnapshot``) capture potential loss:
Historical / Parametric VaR answer *"how much could we lose?"* and Expected
Shortfall answers *"once we enter the worst tail, how much do we lose on
average?"*

The stress testing models (``PositionShock``, ``StressScenario``,
``PositionStressResult`` and ``StressTestResult``) revalue the portfolio
under explicit historical / hypothetical scenarios and classify the stress
loss.

The decision models (``PortfolioRiskDecision``, ``RiskDecision`` and
``PortfolioRiskDecisionEvent``) aggregate limit violations into a single
portfolio-level state: APPROVE / WARNING / REJECT / CRITICAL, and provide a
standard event payload for downstream event buses.

The escalation models (``RiskAction``, ``EscalationLevel``,
``RiskEscalationPolicy`` and ``RiskEscalation``) map a decision onto an
actionable response; the override models (``RiskOverride`` and
``RiskOverridePolicy``) bound manual override authority; ``RiskDecisionTrace``
captures the full audit trail of a risk decision.

The recovery models (``RiskState``, ``RiskRecoveryPolicy``,
``RecoveryAction``, ``RiskRecoveryResult`` and ``RiskRecoveryEvent``) prevent
Risk Flapping by separating the risk control lifecycle from the point-in-time
decision: a breached / critical portfolio must fall below the recovery
threshold, pass consecutive recovery checks and wait out the cooldown window
before returning to NORMAL (hysteresis).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExposureType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class PortfolioExposure:
    portfolio_id: str
    instrument_id: str

    exposure_type: ExposureType

    quantity: Decimal
    market_value: Decimal

    weight: Decimal

    unrealized_pnl: Decimal = ZERO
    realized_pnl: Decimal = ZERO

    leverage: Decimal = Decimal("1")


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    portfolio_id: str
    as_of_date: date

    equity: Decimal

    gross_exposure: Decimal
    net_exposure: Decimal

    gross_leverage: Decimal
    net_leverage: Decimal

    long_exposure: Decimal
    short_exposure: Decimal

    largest_position_weight: Decimal

    risk_level: RiskLevel


@dataclass(frozen=True)
class PortfolioRiskLimit:
    portfolio_id: str

    max_gross_leverage: Decimal
    max_net_leverage: Decimal

    max_position_weight: Decimal

    max_long_exposure: Decimal
    max_short_exposure: Decimal


class RiskLimitType(str, Enum):
    EXPOSURE = "EXPOSURE"
    LEVERAGE = "LEVERAGE"
    CONCENTRATION = "CONCENTRATION"
    FACTOR = "FACTOR"
    VAR = "VAR"
    EXPECTED_SHORTFALL = "EXPECTED_SHORTFALL"
    STRESS_LOSS = "STRESS_LOSS"


class RiskLimitSeverity(str, Enum):
    WARNING = "WARNING"
    BREACH = "BREACH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskLimit:
    limit_id: str

    limit_type: RiskLimitType

    metric: str

    threshold: Decimal

    warning_threshold: Decimal

    hard_limit: Decimal

    enabled: bool = True


@dataclass(frozen=True)
class RiskLimitViolation:
    limit_id: str

    limit_type: RiskLimitType

    metric: str

    actual_value: Decimal

    threshold: Decimal

    severity: RiskLimitSeverity

    message: str


@dataclass(frozen=True)
class RiskLimitAssessment:
    passed: bool

    violations: tuple[
        RiskLimitViolation,
        ...

    ]

    checked_limits: int

    breached_limits: int


@dataclass(frozen=True)
class PortfolioRiskAssessment:
    snapshot: PortfolioRiskSnapshot

    violations: tuple[
        RiskLimitViolation,
        ...
    ]

    within_limits: bool


class ConcentrationRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PositionConcentration:
    instrument_id: str
    weight: Decimal

    sector: str | None = None
    asset_class: str | None = None
    country: str | None = None


@dataclass(frozen=True)
class ConcentrationMetric:
    metric: str

    value: Decimal
    effective_number: Decimal

    risk_level: ConcentrationRiskLevel


class FactorType(str, Enum):
    MARKET = "MARKET"
    SIZE = "SIZE"
    VALUE = "VALUE"
    MOMENTUM = "MOMENTUM"
    QUALITY = "QUALITY"
    VOLATILITY = "VOLATILITY"
    LIQUIDITY = "LIQUIDITY"
    SECTOR = "SECTOR"
    COUNTRY = "COUNTRY"
    CURRENCY = "CURRENCY"
    COMMODITY = "COMMODITY"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class FactorExposure:
    portfolio_id: str
    factor_id: str
    factor_type: FactorType

    exposure: Decimal

    contribution: Decimal = Decimal("0")


@dataclass(frozen=True)
class PositionFactorExposure:
    portfolio_id: str
    instrument_id: str
    factor_id: str

    factor_type: FactorType

    exposure: Decimal


@dataclass(frozen=True)
class FactorRiskContribution:
    factor_id: str
    factor_type: FactorType

    exposure: Decimal
    contribution: Decimal

    contribution_pct: Decimal


@dataclass(frozen=True)
class PortfolioFactorRiskSnapshot:
    portfolio_id: str

    total_factor_risk: Decimal

    factors: tuple[
        FactorRiskContribution,
        ...
    ]


class VaRMethod(str, Enum):
    HISTORICAL = "HISTORICAL"
    PARAMETRIC = "PARAMETRIC"


class TailRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class VaRResult:
    confidence_level: Decimal
    horizon_days: int

    var: Decimal
    method: VaRMethod


@dataclass(frozen=True)
class ExpectedShortfallResult:
    confidence_level: Decimal
    horizon_days: int

    expected_shortfall: Decimal


@dataclass(frozen=True)
class TailRiskSnapshot:
    portfolio_id: str

    var: VaRResult
    expected_shortfall: ExpectedShortfallResult

    tail_risk_level: TailRiskLevel


class ScenarioType(str, Enum):
    HISTORICAL = "HISTORICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    FACTOR = "FACTOR"


class StressRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PositionShock:
    instrument_id: str

    price_shock: Decimal

    volatility_shock: Decimal = Decimal("0")
    fx_shock: Decimal = Decimal("0")


@dataclass(frozen=True)
class StressScenario:
    scenario_id: str
    name: str

    scenario_type: ScenarioType

    shocks: tuple[PositionShock, ...]

    description: str = ""


@dataclass(frozen=True)
class PositionStressResult:
    instrument_id: str

    base_value: Decimal
    stressed_value: Decimal

    pnl_change: Decimal
    pnl_change_pct: Decimal


@dataclass(frozen=True)
class StressTestResult:
    portfolio_id: str
    scenario_id: str

    base_equity: Decimal
    stressed_equity: Decimal

    pnl_change: Decimal
    pnl_change_pct: Decimal

    positions: tuple[
        PositionStressResult,
        ...
    ]

    risk_level: StressRiskLevel


class PortfolioRiskDecision(str, Enum):
    APPROVE = "APPROVE"
    WARNING = "WARNING"
    REJECT = "REJECT"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskDecision:

    decision: PortfolioRiskDecision

    warning_count: int
    breach_count: int
    critical_count: int

    reason: str

    violations: tuple[
        RiskLimitViolation,
        ...
    ]


@dataclass(frozen=True)
class PortfolioRiskDecisionEvent:

    portfolio_id: str

    decision: PortfolioRiskDecision

    warning_count: int
    breach_count: int
    critical_count: int

    reason: str


class RiskAction(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    REDUCE = "REDUCE"
    BLOCK = "BLOCK"
    FREEZE = "FREEZE"


class EscalationLevel(str, Enum):
    NONE = "NONE"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


@dataclass(frozen=True)
class RiskEscalationPolicy:
    policy_id: str

    warning_action: RiskAction
    breach_action: RiskAction
    critical_action: RiskAction

    warning_level: EscalationLevel
    breach_level: EscalationLevel
    critical_level: EscalationLevel

    enabled: bool = True


@dataclass(frozen=True)
class RiskEscalation:
    decision: PortfolioRiskDecision

    action: RiskAction

    level: EscalationLevel

    reason: str


@dataclass(frozen=True)
class RiskOverride:
    override_id: str

    decision: PortfolioRiskDecision

    action: RiskAction

    reason: str

    operator_id: str


@dataclass(frozen=True)
class RiskOverridePolicy:
    allow_warning_override: bool = True
    allow_breach_override: bool = True
    allow_critical_override: bool = False


@dataclass(frozen=True)
class RiskDecisionTrace:
    portfolio_id: str

    decision: PortfolioRiskDecision

    action: RiskAction

    level: EscalationLevel

    metrics: dict[str, Decimal]

    triggered_limits: tuple[str, ...]

    reason: str

    override_id: str | None = None


class RiskState(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    BREACHED = "BREACHED"
    CRITICAL = "CRITICAL"
    RECOVERING = "RECOVERING"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class RiskRecoveryPolicy:

    policy_id: str

    recovery_threshold: Decimal

    cooldown_seconds: int

    required_recovery_checks: int = 3

    enabled: bool = True


class RecoveryAction(str, Enum):
    NONE = "NONE"
    CONTINUE_BLOCK = "CONTINUE_BLOCK"
    REDUCE_ONLY = "REDUCE_ONLY"
    COOLDOWN = "COOLDOWN"
    RESTORE = "RESTORE"


@dataclass(frozen=True)
class RiskRecoveryResult:

    previous_state: RiskState

    current_state: RiskState

    action: RecoveryAction

    recovery_checks: int

    cooldown_remaining_seconds: int

    recovered: bool


@dataclass(frozen=True)
class RiskRecoveryEvent:

    portfolio_id: str

    previous_state: RiskState

    current_state: RiskState

    risk_value: Decimal

    recovery_checks: int

    action: RecoveryAction

    timestamp: float
