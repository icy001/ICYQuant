"""Portfolio risk service (Commit 36).

Application-layer wrapper exposing the risk API: normalizes plain inputs into
``Decimal`` and delegates snapshot / limits assessment to the calculator, plus
concentration analytics (position / sector / asset class / country HHI,
Top-N and largest position), factor risk attribution, tail risk (VaR /
Expected Shortfall), stress testing (Scenario Matrix) and the full risk
decision pipeline: limits -> decision -> escalation -> decision trace, with
recovery lifecycle management (state / hysteresis / cooldown) on top.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .calculator import PortfolioRiskCalculator
from .concentration import (
    ConcentrationRiskCalculator,
)
from .decision import (
    PortfolioRiskDecisionEngine,
)
from .escalation import (
    RiskEscalationEngine,
)
from .factors import (
    FactorRiskCalculator,
)
from .limits import (
    RiskLimitEngine,
)
from .models import (
    ConcentrationMetric,
    PortfolioExposure,
    PortfolioFactorRiskSnapshot,
    PortfolioRiskAssessment,
    PortfolioRiskLimit,
    PortfolioRiskSnapshot,
    PositionConcentration,
    PositionFactorExposure,
    RiskDecisionTrace,
    RiskEscalation,
    RiskEscalationPolicy,
    RiskLimit,
    RiskLimitAssessment,
    RiskRecoveryPolicy,
    RiskState,
    StressScenario,
    StressTestResult,
    TailRiskSnapshot,
)
from .recovery import (
    RecoveryContext,
    RiskRecoveryEngine,
)
from .stress import (
    PortfolioStressCalculator,
)
from .var import (
    PortfolioVaRCalculator,
)


class PortfolioRiskService:

    def __init__(
        self,
        calculator: PortfolioRiskCalculator | None = None,
        concentration_calculator: (
            ConcentrationRiskCalculator | None
        ) = None,
        factor_calculator: (
            FactorRiskCalculator | None
        ) = None,
        var_calculator: (
            PortfolioVaRCalculator | None
        ) = None,
        stress_calculator: (
            PortfolioStressCalculator | None
        ) = None,
        limit_engine: (
            RiskLimitEngine | None
        ) = None,
        decision_engine: (
            PortfolioRiskDecisionEngine | None
        ) = None,
        escalation_engine: (
            RiskEscalationEngine | None
        ) = None,
        recovery_engine: (
            RiskRecoveryEngine | None
        ) = None,
    ) -> None:

        self._calculator = (
            calculator
            or PortfolioRiskCalculator()
        )

        self._concentration_calculator = (
            concentration_calculator
            or ConcentrationRiskCalculator()
        )

        self._factor_calculator = (
            factor_calculator
            or FactorRiskCalculator()
        )

        self._var_calculator = (
            var_calculator
            or PortfolioVaRCalculator()
        )

        self._stress_calculator = (
            stress_calculator
            or PortfolioStressCalculator()
        )

        self._limit_engine = (
            limit_engine
            or RiskLimitEngine()
        )

        self._decision_engine = (
            decision_engine
            or PortfolioRiskDecisionEngine()
        )

        self._escalation_engine = (
            escalation_engine
            or RiskEscalationEngine()
        )

        self._recovery_engine = (
            recovery_engine
            or RiskRecoveryEngine()
        )

    def calculate_snapshot(
        self,
        *,
        portfolio_id: str,
        as_of_date: date,
        equity,
        exposures: list[PortfolioExposure],
    ) -> PortfolioRiskSnapshot:

        return self._calculator.calculate_snapshot(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            equity=Decimal(str(equity)),
            exposures=exposures,
        )

    def assess_limits(
        self,
        *,
        snapshot: PortfolioRiskSnapshot,
        limits: PortfolioRiskLimit,
    ) -> PortfolioRiskAssessment:

        return self._calculator.assess_limits(
            snapshot,
            limits,
        )

    def assess(
        self,
        *,
        portfolio_id: str,
        as_of_date: date,
        equity,
        exposures: list[PortfolioExposure],
        limits: PortfolioRiskLimit,
    ) -> PortfolioRiskAssessment:

        snapshot = self.calculate_snapshot(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            equity=equity,
            exposures=exposures,
        )

        return self.assess_limits(
            snapshot=snapshot,
            limits=limits,
        )

    def calculate_position_concentration(
        self,
        positions: list[PositionConcentration],
    ) -> ConcentrationMetric:

        return (
            self._concentration_calculator
            .calculate_position_concentration(
                positions
            )
        )

    def calculate_group_concentration(
        self,
        positions: list[PositionConcentration],
        *,
        group_by: str,
    ) -> ConcentrationMetric:

        return (
            self._concentration_calculator
            .calculate_group_concentration(
                positions,
                group_by=group_by,
            )
        )

    def calculate_top_n_concentration(
        self,
        positions: list[PositionConcentration],
        *,
        n: int,
    ) -> Decimal:

        return (
            self._concentration_calculator
            .top_n_concentration(
                positions,
                n=n,
            )
        )

    def calculate_factor_risk(
        self,
        exposures: list[PositionFactorExposure],
    ) -> PortfolioFactorRiskSnapshot:

        return (
            self._factor_calculator
            .calculate_risk_contribution(
                exposures
            )
        )

    def calculate_tail_risk(
        self,
        *,
        portfolio_id,
        returns,
        confidence_level=Decimal("0.95"),
        horizon_days=1,
    ) -> TailRiskSnapshot:

        return (
            self._var_calculator
            .calculate_tail_risk(
                portfolio_id=portfolio_id,
                returns=[
                    Decimal(str(value))
                    for value in returns
                ],
                confidence_level=Decimal(
                    str(confidence_level)
                ),
                horizon_days=horizon_days,
            )
        )

    def stress_test(
        self,
        *,
        portfolio_id,
        equity,
        positions,
        scenario: StressScenario,
    ) -> StressTestResult:

        return self._stress_calculator.calculate(
            portfolio_id=portfolio_id,
            equity=Decimal(str(equity)),
            positions={
                instrument_id: Decimal(str(value))
                for instrument_id, value
                in positions.items()
            },
            scenario=scenario,
        )

    def evaluate_risk_limits(
        self,
        *,
        metrics,
        limits: list[RiskLimit],
    ) -> RiskLimitAssessment:

        return self._limit_engine.evaluate(
            metrics=metrics,
            limits=limits,
        )

    def evaluate_risk(
        self,
        *,
        portfolio_id: str,
        metrics,
        limits: list[RiskLimit],
        policy: RiskEscalationPolicy,
    ) -> RiskDecisionTrace:

        assessment = (
            self._limit_engine.evaluate(
                metrics=metrics,
                limits=limits,
            )
        )

        decision = (
            self._decision_engine.evaluate(
                assessment
            )
        )

        escalation = (
            self._escalation_engine.evaluate(
                decision=decision,
                policy=policy,
            )
        )

        return RiskDecisionTrace(
            portfolio_id=portfolio_id,
            decision=decision.decision,
            action=escalation.action,
            level=escalation.level,
            metrics=metrics,
            triggered_limits=tuple(
                violation.limit_id
                for violation
                in assessment.violations
            ),
            reason=escalation.reason,
        )

    def update_recovery_state(
        self,
        *,
        context: RecoveryContext,
        risk_value,
        policy: RiskRecoveryPolicy,
        now: float | None = None,
    ) -> RiskState:

        return self._recovery_engine.update(
            context=context,
            risk_value=Decimal(
                str(risk_value)
            ),
            policy=policy,
            now=now,
        )
