"""
OrderAdmissionService — the final gate that decides whether an order is
eligible to enter the OMS (spec sections 2/8/9/10/12/16).

The evaluation order is fixed:

    Order Request
        ↓
    Validator
        ↓
    Idempotency
        ↓
    Risk Engine
        ↓
    Control Gateway
        ↓
    Position Effect
        ↓
    Admission Decision
        ↓
    Audit
        ↓
    OMS

It can never be reversed: an order that enters the OMS has already mutated
system state.  Risk answers "is this order sound?", the Control Plane answers
"is the system currently allowing this?", and Admission answers "does this
order finally qualify for the OMS?".

Reduce-only is enforced position-aware: the caller's ``is_reduce_only`` flag
is never trusted alone — the position effect (REDUCE / FLATTEN vs INCREASE)
is recomputed from the current position, the side and the quantity.
"""

from __future__ import annotations

from typing import Any, Callable

from services.control_plane.gateway.decision import (
    ControlDecision,
    ControlDecisionReason,
)
from services.control_plane.gateway.gateway import GatewayResult

from .audit import (
    AdmissionAuditEventType,
    AdmissionAuditRecord,
)
from .decision import (
    AdmissionDecision,
    AdmissionReason,
    OrderAdmissionDecision,
)
from .errors import InvalidAdmissionRequestError
from .evidence import AdmissionEvidence
from .policy import AdmissionPolicy
from .position_validator import (
    PositionEffect,
    PositionEffectValidator,
)
from .repository import AdmissionRepository
from .request import OrderAdmissionRequest
from .risk import RiskDecision, RiskResult
from .validator import OrderAdmissionValidator

_FINAL_AUDIT_EVENT = {
    AdmissionDecision.ACCEPTED: (
        AdmissionAuditEventType.ORDER_ADMISSION_ACCEPTED
    ),
    AdmissionDecision.ACCEPTED_REDUCE_ONLY: (
        AdmissionAuditEventType.ORDER_ADMISSION_ACCEPTED_REDUCE_ONLY
    ),
    AdmissionDecision.REJECTED: (
        AdmissionAuditEventType.ORDER_ADMISSION_REJECTED
    ),
}


class OrderAdmissionService:

    def __init__(
        self,
        risk_engine: Any,
        control_gateway: Any,
        policy: AdmissionPolicy | None = None,
        position_provider: Callable[[OrderAdmissionRequest], float] | None = None,
        repository: AdmissionRepository | None = None,
        audit_recorder: Callable[[AdmissionAuditRecord], None] | None = None,
    ):

        self.risk_engine = risk_engine

        self.control_gateway = control_gateway

        self.policy = (
            policy
            or AdmissionPolicy()
        )

        self.position_provider = position_provider

        self.repository = (
            repository
            or AdmissionRepository()
        )

        self.audit_recorder = audit_recorder

        self.validator = (
            OrderAdmissionValidator()
        )

        self.position_validator = (
            PositionEffectValidator()
        )

        self.audit_trail: list[AdmissionAuditRecord] = []

        self.evidence_trail: list[AdmissionEvidence] = []

    # ------------------------------------------------------------------
    # evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        request: OrderAdmissionRequest,
    ) -> OrderAdmissionDecision:

        if not isinstance(request, OrderAdmissionRequest):
            raise InvalidAdmissionRequestError(
                f"expected OrderAdmissionRequest, got {type(request).__name__}"
            )

        self._record_audit(
            AdmissionAuditEventType.ORDER_ADMISSION_REQUESTED,
            request,
        )

        # 1. validation — never evaluate an ill-formed request.
        try:
            self.validator.validate(request)
        except ValueError as exc:
            return self._finalize(
                request,
                self._decision(
                    AdmissionDecision.REJECTED,
                    AdmissionReason.INVALID_REQUEST,
                    request,
                    message=str(exc),
                ),
                risk_result=None,
                control_result=None,
            )

        # 2. idempotency — a retried request_id returns the cached verdict.
        cached = self.repository.get(request.request_id)
        if cached is not None:
            return cached

        # 3. risk engine — "is this order sound?"
        risk_result = self._evaluate_risk(request)

        if risk_result.decision is RiskDecision.REJECTED:
            self._record_audit(
                AdmissionAuditEventType.RISK_REJECTED,
                request,
            )
            return self._finalize(
                request,
                self._decision(
                    AdmissionDecision.REJECTED,
                    AdmissionReason.RISK_REJECTED,
                    request,
                    message=(
                        risk_result.reason
                        or "rejected by risk engine"
                    ),
                    risk_result=risk_result,
                ),
                risk_result=risk_result,
                control_result=None,
            )

        self._record_audit(
            AdmissionAuditEventType.RISK_APPROVED,
            request,
        )

        # 4. control gateway — "is the system currently allowing this?"
        control_result = self._evaluate_control(
            request,
        )
        if control_result is not None:
            self._record_audit(
                AdmissionAuditEventType.CONTROL_EVALUATED,
                request,
            )

        if (
            control_result is not None
            and control_result.decision is ControlDecision.BLOCK
        ):
            return self._finalize(
                request,
                self._decision(
                    AdmissionDecision.REJECTED,
                    AdmissionReason.CONTROL_BLOCKED,
                    request,
                    message="blocked by control gateway",
                    control_result=control_result,
                    risk_result=risk_result,
                ),
                risk_result=risk_result,
                control_result=control_result,
            )

        if (
            control_result is not None
            and control_result.decision is ControlDecision.REDUCE_ONLY
        ):
            return self._evaluate_reduce_only(
                request,
                risk_result=risk_result,
                control_result=control_result,
            )

        if request.is_reduce_only:
            # The request claims to be reduce-only: it may proceed only if the
            # position effect actually reduces risk (spec sections 10/12).
            return self._evaluate_reduce_only(
                request,
                risk_result=risk_result,
                control_result=control_result,
            )

        # 5. allow → accept.
        return self._finalize(
            request,
            self._decision(
                AdmissionDecision.ACCEPTED,
                AdmissionReason.CONTROL_ALLOWED,
                request,
                control_result=control_result,
                risk_result=risk_result,
            ),
            risk_result=risk_result,
            control_result=control_result,
        )

    # ------------------------------------------------------------------
    # reduce-only handling (spec sections 10/12)
    # ------------------------------------------------------------------

    def _evaluate_reduce_only(
        self,
        request: OrderAdmissionRequest,
        *,
        risk_result: RiskResult,
        control_result: Any,
    ) -> OrderAdmissionDecision:

        if not self.policy.allow_reduce_only:
            return self._finalize(
                request,
                self._decision(
                    AdmissionDecision.REJECTED,
                    AdmissionReason.CONTROL_REDUCE_ONLY,
                    request,
                    message=(
                        "reduce-only orders are disabled by policy"
                    ),
                    control_result=control_result,
                    risk_result=risk_result,
                ),
                risk_result=risk_result,
                control_result=control_result,
            )

        # Without a position provider we fall back to the caller's declaration
        # (the base behaviour of spec section 8).  A request that does not even
        # claim reduce-only can never be accepted in reduce-only mode.
        if self.position_provider is None:
            if not request.is_reduce_only:
                return self._finalize(
                    request,
                    self._decision(
                        AdmissionDecision.REJECTED,
                        AdmissionReason.CONTROL_REDUCE_ONLY,
                        request,
                        message=(
                            "new position is not allowed in reduce-only mode"
                        ),
                        control_result=control_result,
                        risk_result=risk_result,
                    ),
                    risk_result=risk_result,
                    control_result=control_result,
                )

            return self._finalize(
                request,
                self._decision(
                    AdmissionDecision.ACCEPTED_REDUCE_ONLY,
                    AdmissionReason.CONTROL_REDUCE_ONLY,
                    request,
                    control_result=control_result,
                    risk_result=risk_result,
                ),
                risk_result=risk_result,
                control_result=control_result,
            )

        # Never trust the caller's flag alone — recompute the position effect.
        current_position = self.position_provider(request)
        effect = self.position_validator.evaluate(
            current_position,
            request.side,
            request.quantity,
        )

        if effect in {PositionEffect.INCREASE, PositionEffect.NONE}:
            return self._finalize(
                request,
                self._decision(
                    AdmissionDecision.REJECTED,
                    AdmissionReason.CONTROL_REDUCE_ONLY,
                    request,
                    message=(
                        "reduce-only: order would increase position "
                        f"(position={current_position}, side={request.side}, "
                        f"qty={request.quantity})"
                    ),
                    control_result=control_result,
                    risk_result=risk_result,
                ),
                risk_result=risk_result,
                control_result=control_result,
            )

        return self._finalize(
            request,
            self._decision(
                AdmissionDecision.ACCEPTED_REDUCE_ONLY,
                AdmissionReason.CONTROL_REDUCE_ONLY,
                request,
                control_result=control_result,
                risk_result=risk_result,
            ),
            risk_result=risk_result,
            control_result=control_result,
        )

    # ------------------------------------------------------------------
    # subsystem evaluation
    # ------------------------------------------------------------------

    def _evaluate_risk(
        self,
        request: OrderAdmissionRequest,
    ) -> RiskResult:

        try:
            raw = self.risk_engine.evaluate(request)
        except Exception as exc:  # noqa: BLE001 - admission must stay total
            return RiskResult(
                decision=RiskDecision.REJECTED,
                reason=f"risk engine failure: {exc}",
            )

        try:
            return RiskResult.of(raw)
        except ValueError:
            return RiskResult(
                decision=RiskDecision.REJECTED,
                reason="risk engine returned an unrecognised decision",
            )

    def _evaluate_control(
        self,
        request: OrderAdmissionRequest,
    ) -> Any:

        if not self.policy.require_control_approval:
            return None

        try:
            return self.control_gateway.evaluate(
                request.context,
                is_new_order=(
                    not request.is_reduce_only
                ),
            )
        except Exception as exc:  # noqa: BLE001 - admission must stay total
            if self.policy.reject_on_gateway_failure:
                return GatewayResult(
                    decision=ControlDecision.BLOCK,
                    reason=ControlDecisionReason.EXECUTION_DISABLED,
                )
            return None

    # ------------------------------------------------------------------
    # decision construction / finalisation
    # ------------------------------------------------------------------

    def _decision(
        self,
        decision: AdmissionDecision,
        reason: AdmissionReason,
        request: OrderAdmissionRequest,
        *,
        message: str = "",
        control_result: Any = None,
        risk_result: Any = None,
    ) -> OrderAdmissionDecision:

        return OrderAdmissionDecision(
            decision=decision,
            reason=reason,
            request_id=request.request_id,
            message=message,
            control_result=control_result,
            risk_result=risk_result,
        )

    def _finalize(
        self,
        request: OrderAdmissionRequest,
        decision: OrderAdmissionDecision,
        *,
        risk_result: Any,
        control_result: Any,
    ) -> OrderAdmissionDecision:

        # Idempotency: the first final verdict is authoritative.
        if not self.repository.has(request.request_id):
            self.repository.save(decision)

        # Evidence: one immutable snapshot per final decision.
        evidence = self._build_evidence(
            request,
            decision,
            risk_result=risk_result,
            control_result=control_result,
        )
        self.evidence_trail.append(evidence)

        # Audit: the terminal event of the sequence.
        self._record_audit(
            _FINAL_AUDIT_EVENT[decision.decision],
            request,
            payload={
                "decision": decision.decision.value,
                "reason": decision.reason.value,
                "message": decision.message,
            },
        )

        return decision

    def _build_evidence(
        self,
        request: OrderAdmissionRequest,
        decision: OrderAdmissionDecision,
        *,
        risk_result: Any,
        control_result: Any,
    ) -> AdmissionEvidence:

        return AdmissionEvidence(
            request_id=request.request_id,
            risk_decision=self._risk_decision_label(risk_result),
            control_decision=self._control_decision_label(control_result),
            final_decision=decision.decision.value,
            reason=decision.reason.value,
        )

    def _record_audit(
        self,
        event_type: AdmissionAuditEventType,
        request: OrderAdmissionRequest,
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:

        record = AdmissionAuditRecord(
            event_type=event_type,
            request_id=request.request_id,
            payload=payload or self._request_payload(request),
        )
        self.audit_trail.append(record)
        if self.audit_recorder is not None:
            try:
                self.audit_recorder(record)
            except Exception:  # noqa: BLE001 - auditing never breaks admission
                pass

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _request_payload(
        request: OrderAdmissionRequest,
    ) -> dict[str, Any]:

        return {
            "symbol": request.symbol,
            "side": request.side,
            "quantity": request.quantity,
            "order_type": request.order_type,
            "is_reduce_only": request.is_reduce_only,
            "account_id": request.context.account_id,
            "strategy_id": request.context.strategy_id,
            "portfolio_id": request.context.portfolio_id,
            "venue": request.context.venue,
            "correlation_id": (
                str(request.context.correlation_id)
                if request.context.correlation_id
                else None
            ),
        }

    @staticmethod
    def _risk_decision_label(risk_result: Any) -> str:
        if risk_result is None:
            return "NOT_EVALUATED"
        raw = getattr(risk_result, "decision", None)
        return getattr(raw, "value", None) or str(raw) or "UNKNOWN"

    @staticmethod
    def _control_decision_label(control_result: Any) -> str:
        if control_result is None:
            return "NOT_EVALUATED"
        raw = getattr(control_result, "decision", None)
        return getattr(raw, "value", None) or str(raw) or "UNKNOWN"
