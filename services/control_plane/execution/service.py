"""
ExecutionControlService — combined Execution → Venue → Routing evaluation
(Commit 26 Part 1.4, spec sections 20, 26).

A new order may reach execution only if:

    Execution = ALLOW  AND  Venue = ALLOW  AND  Routing = AVAILABLE

Any critical layer blocking the request results in REJECT/BLOCK — except for
the risk-reduction actions (cancel / reduce / emergency flatten), which are
never collateral damage of a new-order block.
"""

from __future__ import annotations

from ..routing.controller import RoutingController
from ..venue.controller import VenueController
from ..venue.decision import VenueControlDecision
from .controller import ExecutionController
from .decision import ExecutionControlDecision
from .request import ExecutionAction, ExecutionControlRequest
from .verdict import ExecutionResult, ExecutionVerdict


class ExecutionControlService:

    def __init__(
        self,
        execution_controller: ExecutionController,
        venue_controller: VenueController,
        routing_controller: RoutingController,
    ) -> None:

        self.execution_controller = execution_controller
        self.venue_controller = venue_controller
        self.routing_controller = routing_controller

    def authorize(
        self,
        request: ExecutionControlRequest,
        fallback_venues: list[str] | None = None,
    ) -> ExecutionResult:

        execution_decision = (
            self.execution_controller.evaluate(request.execution_id)
        )
        venue_decision = (
            self.venue_controller.evaluate(request.venue)
        )

        action = request.action

        if action == ExecutionAction.EMERGENCY_FLATTEN.value:
            return self._evaluate_emergency(
                request,
                execution_decision,
                venue_decision,
                fallback_venues,
            )

        if action == ExecutionAction.CANCEL_ORDER.value:
            return self._evaluate_cancel(
                request,
                execution_decision,
                venue_decision,
            )

        if (
            action == ExecutionAction.REDUCE_ORDER.value
            or request.reduce_only
        ):
            return self._evaluate_reduce(
                request,
                execution_decision,
                venue_decision,
            )

        return self._evaluate_new_order(
            request,
            execution_decision,
            venue_decision,
            fallback_venues,
        )

    def _evaluate_new_order(
        self,
        request: ExecutionControlRequest,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
        fallback_venues: list[str] | None,
    ) -> ExecutionResult:

        if (
            execution_decision.allow_new_orders
            and venue_decision.allow_new_orders
        ):
            return ExecutionResult(
                request=request,
                verdict=ExecutionVerdict.ALLOW,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                reason="execution_and_venue_allow_new_orders",
            )

        return self._try_failover(
            request,
            execution_decision,
            venue_decision,
            fallback_venues,
            ExecutionVerdict.REDIRECT,
        )

    def _evaluate_reduce(
        self,
        request: ExecutionControlRequest,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
    ) -> ExecutionResult:

        if (
            execution_decision.allow_reduce_orders
            and venue_decision.allow_reduce_orders
        ):
            return ExecutionResult(
                request=request,
                verdict=ExecutionVerdict.REDUCE_ONLY,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                reason="reduce_orders_allowed",
            )

        return ExecutionResult(
            request=request,
            verdict=ExecutionVerdict.BLOCK,
            execution_decision=execution_decision,
            venue_decision=venue_decision,
            reason="reduce_orders_blocked",
        )

    def _evaluate_cancel(
        self,
        request: ExecutionControlRequest,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
    ) -> ExecutionResult:

        if (
            execution_decision.allow_cancel_orders
            and venue_decision.allow_cancel_orders
        ):
            return ExecutionResult(
                request=request,
                verdict=ExecutionVerdict.CANCEL_ALLOWED,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                reason="cancel_orders_allowed",
            )

        return ExecutionResult(
            request=request,
            verdict=ExecutionVerdict.BLOCK,
            execution_decision=execution_decision,
            venue_decision=venue_decision,
            reason="cancel_orders_blocked",
        )

    def _evaluate_emergency(
        self,
        request: ExecutionControlRequest,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
        fallback_venues: list[str] | None,
    ) -> ExecutionResult:

        if not execution_decision.allow_emergency_flatten:
            return ExecutionResult(
                request=request,
                verdict=ExecutionVerdict.BLOCK,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                reason="emergency_flatten_blocked",
            )

        # 主 venue 自身允许紧急平仓，且未指定备选 venue：
        # 直接在主 venue 执行，不经过路由（平仓是独立的风险降低路径，
        # 不依赖 allow_new_orders）。
        if (
            venue_decision.allow_emergency_flatten
            and not fallback_venues
        ):
            return ExecutionResult(
                request=request,
                verdict=ExecutionVerdict.ALLOW,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                reason="emergency_flatten_allowed_on_primary",
            )

        return self._try_failover(
            request,
            execution_decision,
            venue_decision,
            fallback_venues,
            ExecutionVerdict.EMERGENCY_ROUTE,
            primary_capability="allow_emergency_flatten",
        )

    def _try_failover(
        self,
        request: ExecutionControlRequest,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
        fallback_venues: list[str] | None,
        redirect_verdict: ExecutionVerdict,
        primary_capability: str = "allow_new_orders",
    ) -> ExecutionResult:

        candidates = [request.venue]
        if fallback_venues:
            candidates.extend(
                v for v in fallback_venues if v != request.venue
            )

        route = self.routing_controller.select(candidates)

        if (
            route.allowed
            and route.selected_venue == request.venue
            and getattr(venue_decision, primary_capability)
        ):
            return ExecutionResult(
                request=request,
                verdict=ExecutionVerdict.ALLOW,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                routing_decision=route,
                reason="primary_venue_available",
            )

        if route.allowed and route.selected_venue != request.venue:
            return ExecutionResult(
                request=request,
                verdict=redirect_verdict,
                execution_decision=execution_decision,
                venue_decision=venue_decision,
                routing_decision=route,
                reason="redirected_to_fallback_venue",
            )

        return ExecutionResult(
            request=request,
            verdict=ExecutionVerdict.BLOCK,
            execution_decision=execution_decision,
            venue_decision=venue_decision,
            routing_decision=route,
            reason="no_available_venue",
        )
