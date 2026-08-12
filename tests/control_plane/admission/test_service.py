"""Tests for OrderAdmissionService (spec sections 8/9/10/12/14/17).

Covers the fixed execution chain and the key production scenarios:

    * validation → idempotency → risk → control → position effect → decision
    * risk rejection blocks admission
    * control block rejects the order
    * reduce-only accepts genuine closing orders, rejects position increases
    * the caller's is_reduce_only flag is never trusted alone
    * the same request_id always returns the same decision
    * every decision is audited and evidenced
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from services.control_plane.admission.audit import (
    AdmissionAuditEventType,
)
from services.control_plane.admission.decision import (
    AdmissionDecision,
    AdmissionReason,
)
from services.control_plane.admission.errors import (
    InvalidAdmissionRequestError,
)
from services.control_plane.admission.policy import AdmissionPolicy
from services.control_plane.admission.service import (
    OrderAdmissionService,
)
from services.control_plane.controls.control_type import ControlType
from services.control_plane.controls.scope import ControlScope

from .conftest import (
    BrokenGateway,
    BrokenRiskEngine,
    FakeRiskEngine,
    register_control,
)


class _ReduceOnlyGateway:
    """A control gateway that always returns REDUCE_ONLY."""

    def evaluate(self, context, *, is_new_order=True):
        from services.control_plane.gateway.decision import (
            ControlDecision,
            ControlDecisionReason,
        )
        from services.control_plane.gateway.gateway import GatewayResult

        return GatewayResult(
            decision=ControlDecision.REDUCE_ONLY,
            reason=ControlDecisionReason.REDUCE_ONLY_MODE,
        )


# ----------------------------------------------------------------------
# spec section 17 — core scenarios
# ----------------------------------------------------------------------


def test_risk_rejection_blocks_admission(
    admission_service,
    admission_request,
):
    admission_service.risk_engine = (
        FakeRiskEngine(
            decision="REJECTED"
        )
    )

    result = admission_service.evaluate(
        admission_request
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        result.reason
        is AdmissionReason.RISK_REJECTED
    )


def test_control_block_rejects_order(
    admission_service,
    registry,
    admission_request,
):
    register_control(
        registry,
        ControlType.KILL_SWITCH,
        ControlScope.GLOBAL,
        "GLOBAL",
    )

    result = admission_service.evaluate(
        admission_request
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        result.reason
        is AdmissionReason.CONTROL_BLOCKED
    )


def test_reduce_only_allows_closing_order(
    admission_service,
    admission_request,
):

    admission_request = replace(
        admission_request,
        is_reduce_only=True,
    )

    result = admission_service.evaluate(
        admission_request
    )

    assert (
        result.decision
        is AdmissionDecision.ACCEPTED_REDUCE_ONLY
    )


def test_reduce_only_rejects_position_increase(
    admission_service,
    admission_request,
):

    admission_request = replace(
        admission_request,
        is_reduce_only=True,
        side="BUY",
        quantity=100,
    )

    result = admission_service.evaluate(
        admission_request
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        result.reason
        is AdmissionReason.CONTROL_REDUCE_ONLY
    )


def test_same_request_returns_same_decision(
    admission_service,
    admission_request,
):

    first = admission_service.evaluate(
        admission_request
    )

    second = admission_service.evaluate(
        admission_request
    )

    assert first == second


# ----------------------------------------------------------------------
# happy path
# ----------------------------------------------------------------------


def test_allows_order_when_risk_and_control_pass(
    admission_service,
    admission_request,
):
    result = admission_service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.ACCEPTED
    assert result.reason is AdmissionReason.CONTROL_ALLOWED
    assert result.request_id == admission_request.request_id
    assert result.risk_result is not None
    assert result.control_result is not None


def test_request_is_validated_before_risk(
    admission_service,
    admission_request,
):
    invalid = replace(admission_request, symbol="")

    result = admission_service.evaluate(invalid)

    assert result.decision is AdmissionDecision.REJECTED
    assert result.reason is AdmissionReason.INVALID_REQUEST
    assert result.message == "symbol is required"


def test_invalid_request_never_reaches_risk_engine(
    admission_service,
    admission_request,
):
    invalid = replace(admission_request, quantity=0)

    result = admission_service.evaluate(invalid)

    assert result.decision is AdmissionDecision.REJECTED
    assert result.reason is AdmissionReason.INVALID_REQUEST
    assert admission_service.risk_engine.call_count == 0


# ----------------------------------------------------------------------
# risk engine failures
# ----------------------------------------------------------------------


def test_risk_engine_failure_rejects(
    admission_service,
    admission_request,
):
    admission_service.risk_engine = BrokenRiskEngine()

    result = admission_service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.REJECTED
    assert result.reason is AdmissionReason.RISK_REJECTED
    assert "risk engine failure" in result.message


def test_risk_rejected_carries_reason(
    admission_service,
    admission_request,
):
    admission_service.risk_engine = FakeRiskEngine(
        decision="REJECTED",
        reason="leverage limit breached",
    )

    result = admission_service.evaluate(admission_request)

    assert result.message == "leverage limit breached"


# ----------------------------------------------------------------------
# control failures
# ----------------------------------------------------------------------


def test_gateway_failure_rejects_by_default(
    admission_request,
):
    service = OrderAdmissionService(
        risk_engine=FakeRiskEngine(),
        control_gateway=BrokenGateway(),
    )

    result = service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.REJECTED
    assert result.reason is AdmissionReason.CONTROL_BLOCKED


def test_gateway_failure_allows_when_policy_says_so(
    admission_request,
):
    service = OrderAdmissionService(
        risk_engine=FakeRiskEngine(),
        control_gateway=BrokenGateway(),
        policy=AdmissionPolicy(reject_on_gateway_failure=False),
    )

    result = service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.ACCEPTED


def test_control_approval_can_be_skipped(
    admission_service,
    admission_request,
):
    admission_service.policy = AdmissionPolicy(require_control_approval=False)
    admission_service.control_gateway = BrokenGateway()

    result = admission_service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.ACCEPTED


# ----------------------------------------------------------------------
# reduce-only enforcement (spec sections 10/12)
# ----------------------------------------------------------------------


def test_reduce_only_control_accepts_genuine_reduction(
    admission_service,
    registry,
    admission_request,
):
    register_control(
        registry,
        ControlType.REDUCE_ONLY,
        ControlScope.SYMBOL,
        "NVDA",
    )

    # SELL 50 at +100 → REDUCE; even without the caller's flag the gateway
    # verdict is REDUCE_ONLY and the position effect validates it.
    admission_request = replace(
        admission_request,
        side="SELL",
        quantity=50,
    )

    result = admission_service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.ACCEPTED_REDUCE_ONLY
    assert result.reason is AdmissionReason.CONTROL_REDUCE_ONLY


def test_reduce_only_control_rejects_new_long(
    admission_service,
    registry,
    admission_request,
):
    register_control(
        registry,
        ControlType.REDUCE_ONLY,
        ControlScope.SYMBOL,
        "NVDA",
    )

    admission_request = replace(
        admission_request,
        side="BUY",
        quantity=50,
    )

    result = admission_service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.REJECTED
    assert result.reason is AdmissionReason.CONTROL_REDUCE_ONLY


def test_reduce_only_rejects_when_policy_disallows(
    admission_request,
):
    service = OrderAdmissionService(
        risk_engine=FakeRiskEngine(),
        control_gateway=_ReduceOnlyGateway(),
        policy=AdmissionPolicy(allow_reduce_only=False),
    )

    admission_request = replace(
        admission_request,
        is_reduce_only=True,
        side="SELL",
    )

    result = service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.REJECTED
    assert result.reason is AdmissionReason.CONTROL_REDUCE_ONLY
    assert "disabled by policy" in result.message


# ----------------------------------------------------------------------
# idempotency (spec section 15)
# ----------------------------------------------------------------------


def test_retry_does_not_re_evaluate_risk(
    admission_service,
    admission_request,
):
    first = admission_service.evaluate(admission_request)
    second = admission_service.evaluate(admission_request)

    assert first == second
    assert admission_service.risk_engine.call_count == 1
    assert admission_service.repository.count() == 1


def test_retry_returns_exact_cached_object(
    admission_service,
    admission_request,
):
    first = admission_service.evaluate(admission_request)

    admission_service.risk_engine = FakeRiskEngine(decision="REJECTED")

    second = admission_service.evaluate(admission_request)

    # The cached ACCEPTED verdict wins over the new REJECTED risk engine.
    assert second is first
    assert second.decision is AdmissionDecision.ACCEPTED


# ----------------------------------------------------------------------
# evidence (spec section 13)
# ----------------------------------------------------------------------


def test_every_decision_produces_evidence(
    admission_service,
    admission_request,
):
    admission_service.evaluate(admission_request)

    assert len(admission_service.evidence_trail) == 1
    evidence = admission_service.evidence_trail[0]
    assert evidence.request_id == admission_request.request_id
    assert evidence.risk_decision == "APPROVED"
    assert evidence.control_decision == "ALLOW"
    assert evidence.final_decision == "ACCEPTED"
    assert evidence.reason == "CONTROL_ALLOWED"


def test_rejected_evidence_records_reduce_only_trace(
    admission_service,
    admission_request,
):
    admission_request = replace(
        admission_request,
        is_reduce_only=True,
        side="BUY",
        quantity=100,
    )

    admission_service.evaluate(admission_request)

    evidence = admission_service.evidence_trail[-1]
    assert evidence.risk_decision == "APPROVED"
    assert evidence.control_decision == "ALLOW"
    assert evidence.final_decision == "REJECTED"
    assert evidence.reason == "CONTROL_REDUCE_ONLY"


# ----------------------------------------------------------------------
# audit (spec section 14)
# ----------------------------------------------------------------------


def test_audit_trail_records_acceptance_sequence(
    admission_service,
    admission_request,
):
    admission_service.evaluate(admission_request)

    types = [
        record.event_type
        for record in admission_service.audit_trail
    ]
    assert types == [
        AdmissionAuditEventType.ORDER_ADMISSION_REQUESTED,
        AdmissionAuditEventType.RISK_APPROVED,
        AdmissionAuditEventType.CONTROL_EVALUATED,
        AdmissionAuditEventType.ORDER_ADMISSION_ACCEPTED,
    ]


def test_audit_trail_records_rejection_sequence(
    admission_service,
    admission_request,
):
    admission_service.risk_engine = FakeRiskEngine(decision="REJECTED")

    admission_service.evaluate(admission_request)

    types = [
        record.event_type
        for record in admission_service.audit_trail
    ]
    assert types == [
        AdmissionAuditEventType.ORDER_ADMISSION_REQUESTED,
        AdmissionAuditEventType.RISK_REJECTED,
        AdmissionAuditEventType.ORDER_ADMISSION_REJECTED,
    ]


def test_audit_record_carries_request_payload(
    admission_service,
    admission_request,
):
    admission_service.evaluate(admission_request)

    record = admission_service.audit_trail[0]
    assert record.request_id == admission_request.request_id
    assert record.payload["symbol"] == "NVDA"
    assert record.payload["account_id"] == "ACC001"
    assert record.payload["strategy_id"] == "alpha_nvda"


def test_audit_recorder_receives_records(
    admission_service,
    admission_request,
):
    received: list = []
    admission_service.audit_recorder = received.append

    admission_service.evaluate(admission_request)

    assert len(received) == 4
    assert received[0].event_type is AdmissionAuditEventType.ORDER_ADMISSION_REQUESTED


def test_audit_recorder_failure_does_not_break_admission(
    admission_service,
    admission_request,
):
    def _boom(record):
        raise RuntimeError("audit sink down")

    admission_service.audit_recorder = _boom

    result = admission_service.evaluate(admission_request)

    assert result.decision is AdmissionDecision.ACCEPTED


# ----------------------------------------------------------------------
# misuse / typing
# ----------------------------------------------------------------------


def test_non_request_is_rejected_at_boundary(
    admission_service,
):
    with pytest.raises(InvalidAdmissionRequestError):
        admission_service.evaluate("not a request")  # type: ignore[arg-type]
