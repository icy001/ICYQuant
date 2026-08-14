"""Portfolio concentration risk (Commit 36 Part 1.2).

Answers the question: *"Is the portfolio's risk overly concentrated in a few
places?"* using the Herfindahl-Hirschman Index:

.. code-block:: text

    HHI = Sum(weight^2)
    Effective Number of Positions = 1 / HHI

The same engine is applied at the position level and at any grouping level
(sector / asset class / country), plus largest position and Top-N helpers.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .models import (
    ConcentrationMetric,
    ConcentrationRiskLevel,
    PositionConcentration,
)


ZERO = Decimal("0")


class ConcentrationRiskCalculator:

    def calculate_position_concentration(
        self,
        positions: list[PositionConcentration],
    ) -> ConcentrationMetric:

        if not positions:
            return ConcentrationMetric(
                metric="position_hhi",
                value=ZERO,
                effective_number=ZERO,
                risk_level=ConcentrationRiskLevel.LOW,
            )

        weights = [
            abs(position.weight)
            for position in positions
        ]

        total_weight = sum(weights, ZERO)

        if total_weight == ZERO:
            return ConcentrationMetric(
                metric="position_hhi",
                value=ZERO,
                effective_number=ZERO,
                risk_level=ConcentrationRiskLevel.LOW,
            )

        normalized = [
            weight / total_weight
            for weight in weights
        ]

        hhi = sum(
            weight * weight
            for weight in normalized
        )

        effective_number = (
            ZERO
            if hhi == ZERO
            else Decimal("1") / hhi
        )

        return ConcentrationMetric(
            metric="position_hhi",
            value=hhi,
            effective_number=effective_number,
            risk_level=self._classify_hhi(hhi),
        )

    def calculate_group_concentration(
        self,
        positions: list[PositionConcentration],
        *,
        group_by: str,
    ) -> ConcentrationMetric:

        groups: dict[str, Decimal] = (
            defaultdict(Decimal)
        )

        for position in positions:
            group = getattr(
                position,
                group_by,
                None,
            )

            if group is None:
                raise ValueError(
                    f"Unknown concentration field: "
                    f"{group_by}"
                )

            groups[group] += abs(
                position.weight
            )

        total_weight = sum(
            groups.values(),
            ZERO,
        )

        if total_weight == ZERO:
            return ConcentrationMetric(
                metric=f"{group_by}_hhi",
                value=ZERO,
                effective_number=ZERO,
                risk_level=ConcentrationRiskLevel.LOW,
            )

        normalized = [
            weight / total_weight
            for weight in groups.values()
        ]

        hhi = sum(
            weight * weight
            for weight in normalized
        )

        effective_number = (
            ZERO
            if hhi == ZERO
            else Decimal("1") / hhi
        )

        return ConcentrationMetric(
            metric=f"{group_by}_hhi",
            value=hhi,
            effective_number=effective_number,
            risk_level=self._classify_hhi(hhi),
        )

    @staticmethod
    def largest_position(
        positions: list[PositionConcentration],
    ) -> Decimal:

        return max(
            (
                abs(position.weight)
                for position in positions
            ),
            default=ZERO,
        )

    @staticmethod
    def top_n_concentration(
        positions: list[PositionConcentration],
        *,
        n: int,
    ) -> Decimal:

        if n <= 0:
            raise ValueError(
                "n must be greater than zero"
            )

        weights = sorted(
            (
                abs(position.weight)
                for position in positions
            ),
            reverse=True,
        )

        return sum(
            weights[:n],
            ZERO,
        )

    @staticmethod
    def _classify_hhi(
        hhi: Decimal,
    ) -> ConcentrationRiskLevel:

        if hhi >= Decimal("0.50"):
            return ConcentrationRiskLevel.CRITICAL

        if hhi >= Decimal("0.25"):
            return ConcentrationRiskLevel.HIGH

        if hhi >= Decimal("0.15"):
            return ConcentrationRiskLevel.MEDIUM

        return ConcentrationRiskLevel.LOW
