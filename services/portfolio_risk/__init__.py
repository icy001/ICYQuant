"""Portfolio risk analytics (Commit 36).

Provides the portfolio-level risk domain:

.. code-block:: text

    Exposure -> Leverage -> Risk Snapshot -> Risk Limits -> Risk Assessment
    Concentration (Position / Sector / Asset Class / Country) -> HHI
    Factor Exposure -> Factor Risk Contribution -> Top Factor
    VaR (Historical / Parametric) -> Expected Shortfall -> Tail Risk
    Scenario -> Shock -> Stress PnL -> Stress Risk Level
    Risk Limits -> Violations -> Risk Decision -> Risk Event
    Risk Escalation -> Risk Action -> Decision Trace
    Risk State -> Recovery -> Cooldown -> NORMAL

The ``PortfolioRiskCalculator`` computes snapshots from per-instrument
exposures and assesses them against configured limits; the
``ConcentrationRiskCalculator`` measures how concentrated the portfolio is;
the ``FactorRiskCalculator`` attributes total factor risk to each factor;
the ``PortfolioVaRCalculator`` computes potential loss measures; the
``PortfolioStressCalculator`` revalues the portfolio under scenarios; the
``PortfolioRiskDecisionEngine`` aggregates limit violations into a
portfolio-level decision (APPROVE / WARNING / REJECT / CRITICAL); the
``RiskEscalationEngine`` maps the decision onto an actionable risk action;
the ``RiskRecoveryEngine`` manages the recovery lifecycle (hysteresis /
cooldown) to prevent risk flapping; the ``PortfolioRiskService`` exposes
these capabilities at the application layer.
"""

from .calculator import (
    PortfolioRiskCalculator,
)

from .concentration import (
    ConcentrationRiskCalculator,
)

from .decision import (
    PortfolioRiskDecisionEngine,
)

from .escalation import (
    RiskEscalationEngine,
    RiskOverrideEngine,
)

from .factors import (
    FactorRiskCalculator,
)

from .limits import (
    RiskLimitEngine,
)

from .models import (
    ConcentrationMetric,
    ConcentrationRiskLevel,
    EscalationLevel,
    ExpectedShortfallResult,
    ExposureType,
    FactorExposure,
    FactorRiskContribution,
    FactorType,
    PortfolioExposure,
    PortfolioFactorRiskSnapshot,
    PortfolioRiskAssessment,
    PortfolioRiskDecision,
    PortfolioRiskDecisionEvent,
    PortfolioRiskLimit,
    PortfolioRiskSnapshot,
    PositionConcentration,
    PositionFactorExposure,
    PositionShock,
    PositionStressResult,
    RecoveryAction,
    RiskAction,
    RiskDecision,
    RiskDecisionTrace,
    RiskEscalation,
    RiskEscalationPolicy,
    RiskLevel,
    RiskLimit,
    RiskLimitAssessment,
    RiskLimitSeverity,
    RiskLimitType,
    RiskLimitViolation,
    RiskOverride,
    RiskOverridePolicy,
    RiskRecoveryEvent,
    RiskRecoveryPolicy,
    RiskRecoveryResult,
    RiskState,
    ScenarioType,
    StressRiskLevel,
    StressScenario,
    StressTestResult,
    TailRiskLevel,
    TailRiskSnapshot,
    VaRMethod,
    VaRResult,
)

from .recovery import (
    RecoveryContext,
    RiskRecoveryEngine,
)

from .service import (
    PortfolioRiskService,
)

from .stress import (
    PortfolioStressCalculator,
)

from .var import (
    PortfolioVaRCalculator,
)


__all__ = [
    "ConcentrationMetric",
    "ConcentrationRiskCalculator",
    "ConcentrationRiskLevel",
    "EscalationLevel",
    "ExpectedShortfallResult",
    "ExposureType",
    "FactorExposure",
    "FactorRiskCalculator",
    "FactorRiskContribution",
    "FactorType",
    "PortfolioExposure",
    "PortfolioFactorRiskSnapshot",
    "PortfolioRiskAssessment",
    "PortfolioRiskCalculator",
    "PortfolioRiskDecision",
    "PortfolioRiskDecisionEngine",
    "PortfolioRiskDecisionEvent",
    "PortfolioRiskLimit",
    "PortfolioRiskService",
    "PortfolioRiskSnapshot",
    "PortfolioStressCalculator",
    "PortfolioVaRCalculator",
    "PositionConcentration",
    "PositionFactorExposure",
    "PositionShock",
    "PositionStressResult",
    "RecoveryAction",
    "RecoveryContext",
    "RiskAction",
    "RiskDecision",
    "RiskDecisionTrace",
    "RiskEscalation",
    "RiskEscalationEngine",
    "RiskEscalationPolicy",
    "RiskLevel",
    "RiskLimit",
    "RiskLimitAssessment",
    "RiskLimitEngine",
    "RiskLimitSeverity",
    "RiskLimitType",
    "RiskLimitViolation",
    "RiskOverride",
    "RiskOverrideEngine",
    "RiskOverridePolicy",
    "RiskRecoveryEngine",
    "RiskRecoveryEvent",
    "RiskRecoveryPolicy",
    "RiskRecoveryResult",
    "RiskState",
    "ScenarioType",
    "StressRiskLevel",
    "StressScenario",
    "StressTestResult",
    "TailRiskLevel",
    "TailRiskSnapshot",
    "VaRMethod",
    "VaRResult",
]
