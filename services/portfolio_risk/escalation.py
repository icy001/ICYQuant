"""Risk escalation, override policy and decision trace (Commit 37 Part 1.3).

Maps a ``RiskDecision`` onto an actionable ``RiskEscalation``:

.. code-block:: text

    APPROVE  -> ALLOW / NONE
    WARNING  -> WARN  / L1
    REJECT   -> BLOCK / L2
    CRITICAL -> FREEZE / L4

``RiskEscalationEngine`` applies a ``RiskEscalationPolicy``;
``RiskOverrideEngine`` lets an authorized operator replace the decision /
action while respecting the ``RiskOverridePolicy`` boundary (CRITICAL is not
overridable by default); ``DEFAULT_POLICY`` provides the production default.
"""

from __future__ import annotations

from .models import (
    EscalationLevel,
    PortfolioRiskDecision,
    RiskAction,
    RiskDecision,
    RiskEscalation,
    RiskEscalationPolicy,
    RiskOverride,
    RiskOverridePolicy,
)


DEFAULT_POLICY = RiskEscalationPolicy(
    policy_id="portfolio-default",

    warning_action=RiskAction.WARN,
    breach_action=RiskAction.BLOCK,
    critical_action=RiskAction.FREEZE,

    warning_level=EscalationLevel.L1,
    breach_level=EscalationLevel.L2,
    critical_level=EscalationLevel.L4,
)


class RiskEscalationEngine:

    def evaluate(
        self,
        *,
        decision: RiskDecision,
        policy: RiskEscalationPolicy,
    ) -> RiskEscalation:

        if not policy.enabled:
            return RiskEscalation(
                decision=decision.decision,
                action=RiskAction.ALLOW,
                level=EscalationLevel.NONE,
                reason="Risk escalation policy disabled.",
            )

        if (
            decision.decision
            == PortfolioRiskDecision.CRITICAL
        ):
            return RiskEscalation(
                decision=decision.decision,
                action=policy.critical_action,
                level=policy.critical_level,
                reason=(
                    "Critical risk condition "
                    "requires immediate escalation."
                ),
            )

        if (
            decision.decision
            == PortfolioRiskDecision.REJECT
        ):
            return RiskEscalation(
                decision=decision.decision,
                action=policy.breach_action,
                level=policy.breach_level,
                reason=(
                    "Risk breach requires "
                    "trade restriction."
                ),
            )

        if (
            decision.decision
            == PortfolioRiskDecision.WARNING
        ):
            return RiskEscalation(
                decision=decision.decision,
                action=policy.warning_action,
                level=policy.warning_level,
                reason=(
                    "Risk warning requires "
                    "monitoring."
                ),
            )

        return RiskEscalation(
            decision=decision.decision,
            action=RiskAction.ALLOW,
            level=EscalationLevel.NONE,
            reason="Risk state is within limits.",
        )


class RiskOverrideEngine:

    def apply(
        self,
        *,
        escalation: RiskEscalation,
        override: RiskOverride,
        policy: RiskOverridePolicy,
    ) -> RiskEscalation:

        if (
            escalation.decision
            == PortfolioRiskDecision.CRITICAL
            and not policy.allow_critical_override
        ):
            raise PermissionError(
                "Critical risk cannot be overridden."
            )

        if (
            escalation.decision
            == PortfolioRiskDecision.REJECT
            and not policy.allow_breach_override
        ):
            raise PermissionError(
                "Risk breach cannot be overridden."
            )

        if (
            escalation.decision
            == PortfolioRiskDecision.WARNING
            and not policy.allow_warning_override
        ):
            raise PermissionError(
                "Risk warning cannot be overridden."
            )

        return RiskEscalation(
            decision=override.decision,
            action=override.action,
            level=escalation.level,
            reason=(
                f"Risk override applied: "
                f"{override.reason}"
            ),
        )
