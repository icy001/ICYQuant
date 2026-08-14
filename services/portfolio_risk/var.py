"""Portfolio VaR / Expected Shortfall engine (Commit 36 Part 1.4).

Moves portfolio risk from *"what do we hold / where is the risk?"* to
*"how much could we lose?"*:

.. code-block:: text

    Historical VaR          (no distribution assumption)
    Parametric VaR          (Normal distribution: -(mean - Z * sigma))
    Expected Shortfall      (average loss beyond the VaR cutoff)
        |
        v
    Tail Risk Classification

``PortfolioVaRCalculator`` implements all four capabilities; results are
reported as positive loss magnitudes.
"""

from __future__ import annotations

from decimal import Decimal
from statistics import NormalDist

from .models import (
    ExpectedShortfallResult,
    TailRiskLevel,
    TailRiskSnapshot,
    VaRMethod,
    VaRResult,
)


ZERO = Decimal("0")
ONE = Decimal("1")


class PortfolioVaRCalculator:

    def historical_var(
        self,
        returns: list[Decimal],
        *,
        confidence_level: Decimal = Decimal("0.95"),
        horizon_days: int = 1,
    ) -> VaRResult:

        self._validate(
            returns,
            confidence_level,
            horizon_days,
        )

        sorted_returns = sorted(returns)

        index = int(
            (ONE - confidence_level)
            * Decimal(len(sorted_returns))
        )

        index = max(
            0,
            min(
                index,
                len(sorted_returns) - 1,
            ),
        )

        loss = -sorted_returns[index]

        return VaRResult(
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            var=max(loss, ZERO),
            method=VaRMethod.HISTORICAL,
        )

    def parametric_var(
        self,
        returns: list[Decimal],
        *,
        confidence_level: Decimal = Decimal("0.95"),
        horizon_days: int = 1,
    ) -> VaRResult:

        self._validate(
            returns,
            confidence_level,
            horizon_days,
        )

        mean = self._mean(returns)
        volatility = self._sample_std(returns)

        z_score = Decimal(
            str(
                NormalDist().inv_cdf(
                    float(confidence_level)
                )
            )
        )

        daily_loss = (
            -(mean - z_score * volatility)
        )

        horizon_adjusted = (
            daily_loss
            * Decimal(horizon_days).sqrt()
        )

        return VaRResult(
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            var=max(
                horizon_adjusted,
                ZERO,
            ),
            method=VaRMethod.PARAMETRIC,
        )

    def historical_expected_shortfall(
        self,
        returns: list[Decimal],
        *,
        confidence_level: Decimal = Decimal("0.95"),
        horizon_days: int = 1,
    ) -> ExpectedShortfallResult:

        self._validate(
            returns,
            confidence_level,
            horizon_days,
        )

        sorted_returns = sorted(returns)

        cutoff = int(
            (ONE - confidence_level)
            * Decimal(len(sorted_returns))
        )

        cutoff = max(
            1,
            cutoff,
        )

        tail = sorted_returns[:cutoff]

        average_loss = -(
            sum(tail, ZERO)
            / Decimal(len(tail))
        )

        return ExpectedShortfallResult(
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            expected_shortfall=max(
                average_loss,
                ZERO,
            ),
        )

    def calculate_tail_risk(
        self,
        *,
        portfolio_id: str,
        returns: list[Decimal],
        confidence_level: Decimal = Decimal("0.95"),
        horizon_days: int = 1,
    ) -> TailRiskSnapshot:

        var = self.historical_var(
            returns,
            confidence_level=confidence_level,
            horizon_days=horizon_days,
        )

        expected_shortfall = (
            self.historical_expected_shortfall(
                returns,
                confidence_level=confidence_level,
                horizon_days=horizon_days,
            )
        )

        risk_level = self._classify_tail_risk(
            expected_shortfall.expected_shortfall
        )

        return TailRiskSnapshot(
            portfolio_id=portfolio_id,
            var=var,
            expected_shortfall=expected_shortfall,
            tail_risk_level=risk_level,
        )

    @staticmethod
    def _validate(
        returns: list[Decimal],
        confidence_level: Decimal,
        horizon_days: int,
    ) -> None:

        if not returns:
            raise ValueError(
                "returns must not be empty"
            )

        if not (
            Decimal("0")
            < confidence_level
            < Decimal("1")
        ):
            raise ValueError(
                "confidence_level must be "
                "between 0 and 1"
            )

        if horizon_days <= 0:
            raise ValueError(
                "horizon_days must be "
                "greater than zero"
            )

    @staticmethod
    def _mean(
        values: list[Decimal],
    ) -> Decimal:

        return (
            sum(values, ZERO)
            / Decimal(len(values))
        )

    @staticmethod
    def _sample_std(
        values: list[Decimal],
    ) -> Decimal:

        if len(values) < 2:
            return ZERO

        mean = (
            sum(values, ZERO)
            / Decimal(len(values))
        )

        variance = (
            sum(
                (
                    value - mean
                ) ** 2
                for value in values
            )
            / Decimal(len(values) - 1)
        )

        return variance.sqrt()

    @staticmethod
    def _classify_tail_risk(
        expected_shortfall: Decimal,
    ) -> TailRiskLevel:

        if expected_shortfall >= Decimal("0.10"):
            return TailRiskLevel.CRITICAL

        if expected_shortfall >= Decimal("0.05"):
            return TailRiskLevel.HIGH

        if expected_shortfall >= Decimal("0.02"):
            return TailRiskLevel.MEDIUM

        return TailRiskLevel.LOW
