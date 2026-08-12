"""
InstitutionalControlGateway — the unified safety gate of the whole ICYQuant
trading execution path (spec sections 11/12/18/20/21).

Every trading request — from Strategy Runtime, Risk Engine, OMS, the Incident
Control Plane or a manual operator — must pass through this gateway before it
can reach Execution / the venue.

    Strategy Signal ──► Risk Engine ──► Institutional Control Gateway
                                                    │
                              ┌─────────────┬───────┴─────────┐
                              ▼             ▼                 ▼
                           ALLOW        REDUCE_ONLY         BLOCK
                              │             │                 │
                              ▼             ▼                 ▼
                             OMS            OMS             Audit Event

The gateway is fail-closed: when it degrades, new orders are blocked instead
of being silently allowed.  Decisions are resolved by control *priority*, not
by registration order, and every decision is written to the audit trail so we
can always answer "why did this order not fill?".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..controls.control import ControlAction, is_expired
from ..controls.control_type import ControlType
from ..controls.registry import ControlRegistry
from ..controls.scope import ControlScope

from .context import ControlContext, ControlRequest
from .decision import (
    ControlDecision,
    ControlDecisionReason,
)
from .errors import GatewayError
from .policy import CONTROL_PRIORITY, GatewayPolicy
from .state import GatewayState

# Scope → context attribute → the reason attached to a scoped block.
_CONTEXT_CHECKS = (
    (
        ControlScope.ACCOUNT,
        "account_id",
        ControlDecisionReason.ACCOUNT_BLOCKED,
    ),
    (
        ControlScope.STRATEGY,
        "strategy_id",
        ControlDecisionReason.STRATEGY_DISABLED,
    ),
    (
        ControlScope.SYMBOL,
        "symbol",
        ControlDecisionReason.SYMBOL_BLOCKED,
    ),
    (
        ControlScope.VENUE,
        "venue",
        ControlDecisionReason.VENUE_DISABLED,
    ),
)


@dataclass(frozen=True)
class GatewayResult:

    decision: ControlDecision

    reason: ControlDecisionReason

    matched_control: ControlAction | None = None

    def to_audit_record(
        self,
        context: ControlContext,
    ) -> dict[str, Any]:
        """The audit payload for this decision (spec section 21).

        Example:

            {
                "decision": "BLOCK",
                "reason": "GLOBAL_KILL_SWITCH",
                "strategy_id": "alpha_nvda",
                "symbol": "NVDA",
                "account_id": "ACC001",
            }
        """
        return {
            "decision": self.decision.value,
            "reason": self.reason.value,
            "account_id": context.account_id,
            "portfolio_id": context.portfolio_id,
            "strategy_id": context.strategy_id,
            "symbol": context.symbol,
            "venue": context.venue,
            "order_id": str(context.order_id) if context.order_id else None,
            "correlation_id": (
                str(context.correlation_id) if context.correlation_id else None
            ),
            "control_id": (
                str(self.matched_control.control_id)
                if self.matched_control
                else None
            ),
            "control_type": (
                self.matched_control.control_type.value
                if self.matched_control
                else None
            ),
        }


class InstitutionalControlGateway:

    def __init__(
        self,
        registry: ControlRegistry,
        policy: GatewayPolicy | None = None,
        auditor: Callable[[dict[str, Any]], None] | None = None,
    ):

        self.registry = registry

        self.policy = (
            policy
            or GatewayPolicy()
        )

        self.state = GatewayState.HEALTHY

        self.auditor = auditor

        self.audit_trail: list[dict[str, Any]] = []

        self.failure_reason: str | None = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def degrade(
        self,
        reason: str = "gateway internal failure",
    ) -> None:
        """Transition the gateway into its configured failure posture.

        Fail-closed (default): move to the policy ``fail_safe_state``
        (FAIL_SAFE) which blocks new orders until explicit recovery.
        Fail-open (explicit opt-in): stay HEALTHY and keep admitting traffic.
        """
        self.failure_reason = reason
        if self.policy.fail_open:
            self.state = GatewayState.HEALTHY
        else:
            self.state = self.policy.fail_safe_state

    # ------------------------------------------------------------------
    # evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        context: ControlContext,
        *,
        is_new_order: bool = True,
    ) -> GatewayResult:

        if self.state in {
            GatewayState.FAIL_SAFE,
            GatewayState.DISABLED,
        }:

            if is_new_order:
                return self._record(
                    context,
                    GatewayResult(
                        decision=ControlDecision.BLOCK,
                        reason=ControlDecisionReason.EXECUTION_DISABLED,
                    ),
                )

            # Existing risk-reduction / close flows are not blindly sealed off.
            # They continue through normal evaluation below (spec section 18).

        try:
            result = self._evaluate(
                context,
                is_new_order=is_new_order,
            )
        except Exception as exc:  # noqa: BLE001 - fail-safe must be total
            if self.policy.require_control_registry:
                # Registry is required but unavailable → degrade to fail-safe.
                result = self._evaluate_failure(
                    context,
                    is_new_order=is_new_order,
                    error=exc,
                )
            else:
                # The gateway is explicitly allowed to operate without a
                # registry: no controls → no restriction.
                result = GatewayResult(
                    decision=ControlDecision.ALLOW,
                    reason=ControlDecisionReason.NO_ACTIVE_CONTROL,
                )

        return self._record(context, result)

    def admit(
        self,
        request: ControlRequest,
    ) -> GatewayResult:
        """Evaluate a unified ``ControlRequest`` (spec section 19)."""
        if not isinstance(request, ControlRequest):
            raise GatewayError(
                f"expected ControlRequest, got {type(request).__name__}"
            )
        return self.evaluate(
            request.context,
            is_new_order=request.is_new_order,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        context: ControlContext,
        *,
        is_new_order: bool,
    ) -> GatewayResult:

        candidates: list[tuple[ControlAction, GatewayResult]] = []

        # Global controls first — the widest net.
        for control in self.registry.active(
            scope=ControlScope.GLOBAL,
            target="GLOBAL",
        ):
            if self._expired(control):
                continue
            result = self._global_result(
                control,
                is_new_order=is_new_order,
            )
            if result is not None:
                candidates.append((control, result))

        # Then scoped controls.
        for scope, attribute, reason in _CONTEXT_CHECKS:

            target = getattr(context, attribute, None)
            if target is None:
                continue

            for control in self.registry.active(
                scope=scope,
                target=target,
            ):
                if self._expired(control):
                    continue
                result = self._scoped_result(
                    control,
                    is_new_order=is_new_order,
                    reason=reason,
                )
                if result is not None:
                    candidates.append((control, result))

        if not candidates:
            return GatewayResult(
                decision=ControlDecision.ALLOW,
                reason=ControlDecisionReason.NO_ACTIVE_CONTROL,
            )

        # Highest priority wins — independent of registration order.
        best_control, best_result = max(
            candidates,
            key=lambda pair: CONTROL_PRIORITY.get(
                pair[0].control_type, 0
            ),
        )
        return best_result

    def _global_result(
        self,
        control: ControlAction,
        *,
        is_new_order: bool,
    ) -> GatewayResult | None:

        ctype = control.control_type

        if ctype is ControlType.KILL_SWITCH:
            return GatewayResult(
                decision=ControlDecision.BLOCK,
                reason=ControlDecisionReason.GLOBAL_KILL_SWITCH,
                matched_control=control,
            )

        if ctype is ControlType.DISABLE_EXECUTION:
            return GatewayResult(
                decision=ControlDecision.BLOCK,
                reason=ControlDecisionReason.EXECUTION_DISABLED,
                matched_control=control,
            )

        if ctype is ControlType.BLOCK_NEW_ORDERS:
            if is_new_order:
                return GatewayResult(
                    decision=ControlDecision.BLOCK,
                    reason=ControlDecisionReason.EXECUTION_DISABLED,
                    matched_control=control,
                )
            return None

        if ctype in {
            ControlType.DISABLE_STRATEGY,
            ControlType.PAUSE_STRATEGY,
        }:
            if is_new_order:
                return GatewayResult(
                    decision=ControlDecision.BLOCK,
                    reason=ControlDecisionReason.STRATEGY_DISABLED,
                    matched_control=control,
                )
            return None

        if ctype is ControlType.REDUCE_ONLY:
            if is_new_order:
                return GatewayResult(
                    decision=ControlDecision.REDUCE_ONLY,
                    reason=ControlDecisionReason.REDUCE_ONLY_MODE,
                    matched_control=control,
                )
            return None

        return None

    def _scoped_result(
        self,
        control: ControlAction,
        *,
        is_new_order: bool,
        reason: ControlDecisionReason,
    ) -> GatewayResult | None:

        ctype = control.control_type

        if ctype is ControlType.KILL_SWITCH:
            # A kill switch is a hard gate wherever it is attached.
            return GatewayResult(
                decision=ControlDecision.BLOCK,
                reason=ControlDecisionReason.GLOBAL_KILL_SWITCH,
                matched_control=control,
            )

        if ctype in {
            ControlType.BLOCK_NEW_ORDERS,
            ControlType.DISABLE_STRATEGY,
            ControlType.DISABLE_EXECUTION,
            ControlType.PAUSE_STRATEGY,
        }:
            # Scoped controls always carry the scope-specific reason
            # (ACCOUNT_BLOCKED / STRATEGY_DISABLED / SYMBOL_BLOCKED /
            # VENUE_DISABLED) — e.g. a VENUE-scoped DISABLE_EXECUTION
            # surfaces as VENUE_DISABLED.
            if is_new_order:
                return GatewayResult(
                    decision=ControlDecision.BLOCK,
                    reason=reason,
                    matched_control=control,
                )
            return None

        if ctype is ControlType.REDUCE_ONLY:
            if is_new_order:
                return GatewayResult(
                    decision=ControlDecision.REDUCE_ONLY,
                    reason=ControlDecisionReason.REDUCE_ONLY_MODE,
                    matched_control=control,
                )
            return None

        return None

    def _evaluate_failure(
        self,
        context: ControlContext,
        *,
        is_new_order: bool,
        error: Exception,
    ) -> GatewayResult:

        self.degrade(str(error) or "gateway internal failure")

        if self.policy.fail_open:
            return GatewayResult(
                decision=ControlDecision.ALLOW,
                reason=ControlDecisionReason.NO_ACTIVE_CONTROL,
            )

        if is_new_order:
            return GatewayResult(
                decision=ControlDecision.BLOCK,
                reason=ControlDecisionReason.EXECUTION_DISABLED,
            )

        # Reduce-only / close flows keep flowing even under fail-safe.
        return GatewayResult(
            decision=ControlDecision.ALLOW,
            reason=ControlDecisionReason.NO_ACTIVE_CONTROL,
        )

    def _expired(self, control: ControlAction) -> bool:
        """Expired temporary controls are ignored by the gateway.

        KILL_SWITCH never auto-expires: it requires explicit, authorized
        clearing (spec sections 16/17).
        """
        if control.control_type is ControlType.KILL_SWITCH:
            return False
        return is_expired(control)

    def _record(
        self,
        context: ControlContext,
        result: GatewayResult,
    ) -> GatewayResult:

        record = result.to_audit_record(context)
        self.audit_trail.append(record)
        if self.auditor is not None:
            try:
                self.auditor(record)
            except Exception:  # noqa: BLE001 - auditing must not break gating
                pass
        return result
