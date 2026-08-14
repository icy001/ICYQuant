"""Portfolio risk decision engine (Commit 37 Part 1.2).

Aggregates ``RiskLimitViolation`` counts into a single portfolio-level
decision:

.. code-block:: text

    Risk Metrics -> Risk Limits -> Limit Violations
        -> Risk Breach Aggregation -> Portfolio Risk Decision

``PortfolioRiskDecisionEngine`` counts WARNING / BREACH / CRITICAL
violations and applies the decision priority:

.. code-block:: text

    CRITICAL > REJECT (BREACH) > WARNING > APPROVE

The result is a ``RiskDecision`` with explicit counts and a human-readable
reason, replacing the boolean ``passed`` with an actionable state:
APPROVE / WARNING / REJECT / CRITICAL.
"""

from __future__ import annotations

from .models import (
    PortfolioRiskDecision,
    RiskDecision,
    RiskLimitAssessment,
    RiskLimitSeverity,
)


class PortfolioRiskDecisionEngine:

    def evaluate(
        self,
        assessment: RiskLimitAssessment,
    ) -> RiskDecision:

        warning_count = 0
        breach_count = 0
        critical_count = 0

        for violation in assessment.violations:

            if (
                violation.severity
                == RiskLimitSeverity.WARNING
            ):
                warning_count += 1

            elif (
                violation.severity
                == RiskLimitSeverity.BREACH
            ):
                breach_count += 1

            elif (
                violation.severity
                == RiskLimitSeverity.CRITICAL
            ):
                critical_count += 1

        if critical_count > 0:

            decision = (
                PortfolioRiskDecision.CRITICAL
            )

            reason = (
                "One or more critical "
                "risk limits were breached."
            )

        elif breach_count > 0:

            decision = (
                PortfolioRiskDecision.REJECT
            )

            reason = (
                "One or more hard risk "
                "limits were breached."
            )

        elif warning_count > 0:

            decision = (
                PortfolioRiskDecision.WARNING
            )

            reason = (
                "One or more risk limits "
                "entered warning range."
            )

        else:

            decision = (
                PortfolioRiskDecision.APPROVE
            )

            reason = (
                "All enabled risk limits "
                "passed."
            )

        return RiskDecision(
            decision=decision,
            warning_count=warning_count,
            breach_count=breach_count,
            critical_count=critical_count,
            reason=reason,
            violations=assessment.violations,
        )
