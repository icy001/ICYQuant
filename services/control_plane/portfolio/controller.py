"""
PortfolioController — per-portfolio risk posture gate
(Commit 26 Part 1.3, spec sections 13, 21–22).

Portfolio is the layer above strategy: a frozen or liquidating portfolio
constrains every strategy beneath it.  This controller is the authoritative
source of the portfolio's current risk posture and evaluates the granular
capabilities derived from that posture.

``RECOVERING`` intentionally evaluates as fail-closed (no trading capability)
until an authorized operator explicitly returns the portfolio to ACTIVE.
"""

from __future__ import annotations

from uuid import UUID

from .audit import (
    PortfolioControlAuditRecord,
    audit_event_type_for,
)
from .decision import PortfolioControlDecision
from .policy import PortfolioControlPolicy
from .state import PortfolioState


class PortfolioController:

    def __init__(
        self,
        policy: PortfolioControlPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            or PortfolioControlPolicy()
        )

        self._states: dict[str, PortfolioState] = {}

        self._audit_trail: list[PortfolioControlAuditRecord] = []

    def state(
        self,
        portfolio_id: str,
    ) -> PortfolioState:

        return self._states.get(
            portfolio_id,
            PortfolioState.ACTIVE,
        )

    def set_state(
        self,
        portfolio_id: str,
        state: PortfolioState,
        *,
        incident_id: UUID | None = None,
        control_id: UUID | None = None,
        actor: str = "portfolio-controller",
        reason: str = "",
    ) -> None:

        previous_state = self.state(portfolio_id)
        self._states[portfolio_id] = state

        if previous_state is not state:
            self._audit_trail.append(
                PortfolioControlAuditRecord(
                    event_type=audit_event_type_for(state),
                    portfolio_id=portfolio_id,
                    previous_state=previous_state,
                    new_state=state,
                    incident_id=incident_id,
                    control_id=control_id,
                    actor=actor,
                    reason=reason,
                )
            )

    def evaluate(
        self,
        portfolio_id: str,
    ) -> PortfolioControlDecision:

        state = self.state(portfolio_id)

        if state == PortfolioState.ACTIVE:

            return PortfolioControlDecision(
                portfolio_id=portfolio_id,
                current_state=state,
                allow_new_risk=True,
                allow_new_orders=True,
                allow_reduce_orders=True,
                allow_liquidation=True,
                reason="portfolio_active",
            )

        if state == PortfolioState.RESTRICTED:

            return PortfolioControlDecision(
                portfolio_id=portfolio_id,
                current_state=state,
                allow_new_risk=(
                    self.policy.restricted_allow_new_risk
                ),
                allow_new_orders=(
                    self.policy.restricted_allow_new_orders
                ),
                allow_reduce_orders=(
                    self.policy.restricted_allow_reduce
                ),
                allow_liquidation=True,
                reason="portfolio_restricted",
            )

        if state == PortfolioState.REDUCE_ONLY:

            return PortfolioControlDecision(
                portfolio_id=portfolio_id,
                current_state=state,
                allow_new_risk=False,
                allow_new_orders=False,
                allow_reduce_orders=(
                    self.policy.reduce_only_allow_reduce
                ),
                allow_liquidation=True,
                reason="portfolio_reduce_only",
            )

        if state == PortfolioState.FROZEN:

            return PortfolioControlDecision(
                portfolio_id=portfolio_id,
                current_state=state,
                allow_new_risk=False,
                allow_new_orders=False,
                allow_reduce_orders=(
                    self.policy.frozen_allow_reduce
                ),
                allow_liquidation=True,
                reason="portfolio_frozen",
            )

        if state == PortfolioState.LIQUIDATING:

            return PortfolioControlDecision(
                portfolio_id=portfolio_id,
                current_state=state,
                allow_new_risk=False,
                allow_new_orders=False,
                allow_reduce_orders=(
                    self.policy.liquidating_allow_reduce
                ),
                allow_liquidation=True,
                reason="portfolio_liquidating",
            )

        return PortfolioControlDecision(
            portfolio_id=portfolio_id,
            current_state=state,
            allow_new_risk=False,
            allow_new_orders=False,
            allow_reduce_orders=False,
            allow_liquidation=False,
            reason="unknown_portfolio_state",
        )

    @property
    def audit_trail(
        self,
    ) -> list[PortfolioControlAuditRecord]:
        """Immutable view of the state-transition audit trail."""
        return list(self._audit_trail)
