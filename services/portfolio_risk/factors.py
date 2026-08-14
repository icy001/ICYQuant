"""Portfolio factor exposure and risk attribution (Commit 36 Part 1.3).

Answers the question: *"Where does the portfolio's risk actually come
from?"* by moving beyond positions into factor space:

.. code-block:: text

    Position
        |
        v
    Factor Exposure        (per position x factor)
        |
        v
    Factor Aggregation     (sum per factor across positions)
        |
        v
    Factor Risk Contribution = |Exposure_i| / Sum(|Exposure|)
        |
        v
    Top Factor

``FactorRiskCalculator`` aggregates per-position factor exposures and
attributes the total factor risk back to the underlying factors.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .models import (
    FactorRiskContribution,
    PortfolioFactorRiskSnapshot,
    PositionFactorExposure,
)


ZERO = Decimal("0")


class FactorRiskCalculator:

    def aggregate_exposure(
        self,
        exposures: list[PositionFactorExposure],
    ) -> dict[str, Decimal]:

        result: dict[str, Decimal] = (
            defaultdict(Decimal)
        )

        for exposure in exposures:
            result[
                exposure.factor_id
            ] += exposure.exposure

        return dict(result)

    def calculate_risk_contribution(
        self,
        exposures: list[PositionFactorExposure],
    ) -> PortfolioFactorRiskSnapshot:

        if not exposures:
            return PortfolioFactorRiskSnapshot(
                portfolio_id="",
                total_factor_risk=ZERO,
                factors=(),
            )

        portfolio_ids = {
            exposure.portfolio_id
            for exposure in exposures
        }

        if len(portfolio_ids) != 1:
            raise ValueError(
                "All factor exposures must "
                "belong to the same portfolio"
            )

        portfolio_id = (
            next(iter(portfolio_ids))
        )

        grouped: dict[
            str,
            Decimal
        ] = defaultdict(Decimal)

        factor_types = {}

        for exposure in exposures:

            grouped[
                exposure.factor_id
            ] += exposure.exposure

            factor_types[
                exposure.factor_id
            ] = exposure.factor_type

        absolute_total = sum(
            (
                abs(value)
                for value in grouped.values()
            ),
            ZERO,
        )

        if absolute_total == ZERO:
            return PortfolioFactorRiskSnapshot(
                portfolio_id=portfolio_id,
                total_factor_risk=ZERO,
                factors=tuple(),
            )

        factors = []

        for factor_id, exposure in grouped.items():

            contribution = abs(exposure)

            contribution_pct = (
                contribution
                / absolute_total
            )

            factors.append(
                FactorRiskContribution(
                    factor_id=factor_id,
                    factor_type=factor_types[
                        factor_id
                    ],
                    exposure=exposure,
                    contribution=contribution,
                    contribution_pct=contribution_pct,
                )
            )

        factors.sort(
            key=lambda item: abs(
                item.contribution
            ),
            reverse=True,
        )

        return PortfolioFactorRiskSnapshot(
            portfolio_id=portfolio_id,
            total_factor_risk=absolute_total,
            factors=tuple(factors),
        )

    @staticmethod
    def top_factor(
        snapshot: PortfolioFactorRiskSnapshot,
    ) -> FactorRiskContribution | None:

        if not snapshot.factors:
            return None

        return snapshot.factors[0]
