"""Portfolio risk calculator (Commit 36).

Computes portfolio risk snapshots from per-instrument exposures and assesses
them against configured risk limits, plus factor-level risk attribution,
VaR / Expected Shortfall tail risk and stress testing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .decision import (
    PortfolioRiskDecisionEngine,
)
from .factors import FactorRiskCalculator
from .limits import RiskLimitEngine
from .models import (
    ExpectedShortfallResult,
    ExposureType,
    PortfolioExposure,
    PortfolioFactorRiskSnapshot,
    PortfolioRiskAssessment,
    PortfolioRiskLimit,
    PortfolioRiskSnapshot,
    PositionFactorExposure,
    RiskDecision,
    RiskLevel,
    RiskLimitAssessment,
    RiskLimitSeverity,
    RiskLimitType,
    RiskLimitViolation,
    StressScenario,
    StressTestResult,
    VaRResult,
)
from .stress import PortfolioStressCalculator
from .var import PortfolioVaRCalculator


ZERO = Decimal("0")


class PortfolioRiskCalculator:

    def __init__(
        self,
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
    ) -> None:

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

    def calculate_snapshot(
        self,
        *,
        portfolio_id: str,
        as_of_date: date,
        equity: Decimal,
        exposures: list[PortfolioExposure],
    ) -> PortfolioRiskSnapshot:

        if equity <= ZERO:
            raise ValueError(
                "equity must be greater than zero"
            )

        if any(
            exposure.portfolio_id
            != portfolio_id
            for exposure in exposures
        ):
            raise ValueError(
                "All exposures must belong "
                "to the same portfolio"
            )

        long_exposure = sum(
            (
                abs(exposure.market_value)
                for exposure in exposures
                if exposure.exposure_type
                == ExposureType.LONG
            ),
            ZERO,
        )

        short_exposure = sum(
            (
                abs(exposure.market_value)
                for exposure in exposures
                if exposure.exposure_type
                == ExposureType.SHORT
            ),
            ZERO,
        )

        gross_exposure = (
            long_exposure
            + short_exposure
        )

        net_exposure = (
            long_exposure
            - short_exposure
        )

        gross_leverage = (
            gross_exposure / equity
        )

        net_leverage = (
            abs(net_exposure) / equity
        )

        largest_position_weight = max(
            (
                abs(exposure.weight)
                for exposure in exposures
            ),
            default=ZERO,
        )

        risk_level = self._classify_risk(
            gross_leverage=gross_leverage,
            net_leverage=net_leverage,
            largest_position_weight=(
                largest_position_weight
            ),
        )

        return PortfolioRiskSnapshot(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            equity=equity,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            gross_leverage=gross_leverage,
            net_leverage=net_leverage,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            largest_position_weight=(
                largest_position_weight
            ),
            risk_level=risk_level,
        )

    def assess_limits(
        self,
        snapshot: PortfolioRiskSnapshot,
        limits: PortfolioRiskLimit,
    ) -> PortfolioRiskAssessment:

        if (
            snapshot.portfolio_id
            != limits.portfolio_id
        ):
            raise ValueError(
                "Snapshot and limits must "
                "belong to the same portfolio"
            )

        violations: list[
            RiskLimitViolation
        ] = []

        if (
            snapshot.gross_leverage
            > limits.max_gross_leverage
        ):
            violations.append(
                RiskLimitViolation(
                    limit_id="gross-leverage-limit",
                    limit_type=RiskLimitType.LEVERAGE,
                    metric="gross_leverage",
                    actual_value=(
                        snapshot.gross_leverage
                    ),
                    threshold=(
                        limits.max_gross_leverage
                    ),
                    severity=RiskLimitSeverity.BREACH,
                    message=(
                        "Gross leverage exceeds "
                        "the configured limit"
                    ),
                )
            )

        if (
            snapshot.net_leverage
            > limits.max_net_leverage
        ):
            violations.append(
                RiskLimitViolation(
                    limit_id="net-leverage-limit",
                    limit_type=RiskLimitType.LEVERAGE,
                    metric="net_leverage",
                    actual_value=(
                        snapshot.net_leverage
                    ),
                    threshold=(
                        limits.max_net_leverage
                    ),
                    severity=RiskLimitSeverity.BREACH,
                    message=(
                        "Net leverage exceeds "
                        "the configured limit"
                    ),
                )
            )

        if (
            snapshot.largest_position_weight
            > limits.max_position_weight
        ):
            violations.append(
                RiskLimitViolation(
                    limit_id="position-weight-limit",
                    limit_type=RiskLimitType.CONCENTRATION,
                    metric="position_weight",
                    actual_value=(
                        snapshot.largest_position_weight
                    ),
                    threshold=(
                        limits.max_position_weight
                    ),
                    severity=RiskLimitSeverity.BREACH,
                    message=(
                        "Largest position exceeds "
                        "the configured limit"
                    ),
                )
            )

        if (
            snapshot.long_exposure
            > limits.max_long_exposure
        ):
            violations.append(
                RiskLimitViolation(
                    limit_id="long-exposure-limit",
                    limit_type=RiskLimitType.EXPOSURE,
                    metric="long_exposure",
                    actual_value=(
                        snapshot.long_exposure
                    ),
                    threshold=(
                        limits.max_long_exposure
                    ),
                    severity=RiskLimitSeverity.BREACH,
                    message=(
                        "Long exposure exceeds "
                        "the configured limit"
                    ),
                )
            )

        if (
            snapshot.short_exposure
            > limits.max_short_exposure
        ):
            violations.append(
                RiskLimitViolation(
                    limit_id="short-exposure-limit",
                    limit_type=RiskLimitType.EXPOSURE,
                    metric="short_exposure",
                    actual_value=(
                        snapshot.short_exposure
                    ),
                    threshold=(
                        limits.max_short_exposure
                    ),
                    severity=RiskLimitSeverity.BREACH,
                    message=(
                        "Short exposure exceeds "
                        "the configured limit"
                    ),
                )
            )

        return PortfolioRiskAssessment(
            snapshot=snapshot,
            violations=tuple(violations),
            within_limits=(
                len(violations) == 0
            ),
        )

    def evaluate_limits(
        self,
        *,
        metrics,
        limits,
    ) -> RiskLimitAssessment:

        return self._limit_engine.evaluate(
            metrics=metrics,
            limits=limits,
        )

    def evaluate_decision(
        self,
        assessment,
    ) -> RiskDecision:

        return self._decision_engine.evaluate(
            assessment
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

    def historical_var(
        self,
        returns,
        *,
        confidence_level=Decimal("0.95"),
        horizon_days=1,
    ) -> VaRResult:

        return self._var_calculator.historical_var(
            [
                Decimal(str(value))
                for value in returns
            ],
            confidence_level=Decimal(
                str(confidence_level)
            ),
            horizon_days=horizon_days,
        )

    def parametric_var(
        self,
        returns,
        *,
        confidence_level=Decimal("0.95"),
        horizon_days=1,
    ) -> VaRResult:

        return self._var_calculator.parametric_var(
            [
                Decimal(str(value))
                for value in returns
            ],
            confidence_level=Decimal(
                str(confidence_level)
            ),
            horizon_days=horizon_days,
        )

    def expected_shortfall(
        self,
        returns,
        *,
        confidence_level=Decimal("0.95"),
        horizon_days=1,
    ) -> ExpectedShortfallResult:

        return (
            self._var_calculator
            .historical_expected_shortfall(
                [
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

    @staticmethod
    def _classify_risk(
        *,
        gross_leverage: Decimal,
        net_leverage: Decimal,
        largest_position_weight: Decimal,
    ) -> RiskLevel:

        if (
            gross_leverage >= Decimal("5")
            or net_leverage >= Decimal("4")
            or largest_position_weight >= Decimal("0.50")
        ):
            return RiskLevel.CRITICAL

        if (
            gross_leverage >= Decimal("3")
            or net_leverage >= Decimal("2")
            or largest_position_weight >= Decimal("0.30")
        ):
            return RiskLevel.HIGH

        if (
            gross_leverage >= Decimal("1.5")
            or net_leverage >= Decimal("1")
            or largest_position_weight >= Decimal("0.20")
        ):
            return RiskLevel.MEDIUM

        return RiskLevel.LOW
