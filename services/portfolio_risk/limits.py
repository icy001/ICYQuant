"""Portfolio risk limit enforcement (Commit 37 Part 1.1).

Moves from *"computing"* risk to *"judging"* it against policy:

.. code-block:: text

    Risk Metrics -> Risk Limits -> Risk Limit Engine -> Violation
        (WARNING / BREACH / CRITICAL)

``RiskLimitEngine`` evaluates a set of named metrics against a list of
``RiskLimit`` definitions. Each limit carries three thresholds:

* ``warning_threshold`` - approaching the boundary
* ``threshold``          - breach
* ``hard_limit``         - critical

Unknown metrics and disabled limits are skipped; only evaluated limits are
counted in ``checked_limits``.
"""

from __future__ import annotations

from decimal import Decimal

from .models import (
    RiskLimit,
    RiskLimitAssessment,
    RiskLimitSeverity,
    RiskLimitViolation,
)


ZERO = Decimal("0")


class RiskLimitEngine:

    def evaluate(
        self,
        *,
        metrics: dict[str, Decimal],
        limits: list[RiskLimit],
    ) -> RiskLimitAssessment:

        violations = []

        checked_limits = 0

        for limit in limits:

            if not limit.enabled:
                continue

            checked_limits += 1

            actual_value = metrics.get(
                limit.metric
            )

            if actual_value is None:
                continue

            severity = self._severity(
                actual_value=actual_value,
                limit=limit,
            )

            if severity is None:
                continue

            violations.append(
                RiskLimitViolation(
                    limit_id=limit.limit_id,
                    limit_type=limit.limit_type,
                    metric=limit.metric,
                    actual_value=actual_value,
                    threshold=limit.threshold,
                    severity=severity,
                    message=self._message(
                        limit,
                        actual_value,
                        severity,
                    ),
                )
            )

        return RiskLimitAssessment(
            passed=not violations,
            violations=tuple(violations),
            checked_limits=checked_limits,
            breached_limits=len(violations),
        )

    @staticmethod
    def _severity(
        *,
        actual_value: Decimal,
        limit: RiskLimit,
    ) -> RiskLimitSeverity | None:

        if actual_value >= limit.hard_limit:
            return RiskLimitSeverity.CRITICAL

        if actual_value >= limit.threshold:
            return RiskLimitSeverity.BREACH

        if actual_value >= limit.warning_threshold:
            return RiskLimitSeverity.WARNING

        return None

    @staticmethod
    def _message(
        limit: RiskLimit,
        actual_value: Decimal,
        severity: RiskLimitSeverity,
    ) -> str:

        return (
            f"{severity.value}: "
            f"{limit.metric}={actual_value} "
            f"exceeds "
            f"{limit.warning_threshold}"
        )
