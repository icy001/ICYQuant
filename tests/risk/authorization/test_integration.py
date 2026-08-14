"""End-to-end tests for the authorization integration boundary (Commit 31
Part 1.5).
"""

from typing import Optional

import pytest

from services.risk.authorization.certificate import (
    AuthorizationCertificateIssuer,
    ExecutionAuthorizationCertificate,
)
from services.risk.authorization.contract import RiskAuthorizationRequest, new_request_id
from services.risk.authorization.decision import approved_decision, rejected_decision
from services.risk.authorization.errors import AuthorizationErrorCode
from services.risk.authorization.integration import (
    AuthorizedExecutionContext,
    AuthorizationIntegrationService,
    AuthorizationResult,
)
from services.risk.authorization.validator import ExecutionRequest


def valid_request(**overrides) -> RiskAuthorizationRequest:
    defaults = dict(
        request_id="RAUTH-001",
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        target_quantity=100.0,
        execution_policy="MARKET",
        urgency="NORMAL",
        submitted_at=1000.0,
    )
    defaults.update(overrides)
    return RiskAuthorizationRequest(**defaults)


def approved_execution_request(**overrides) -> ExecutionRequest:
    defaults = dict(
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        quantity=100.0,
        execution_policy="MARKET",
        idempotency_key="STRAT-001:SESSION-001:INT-001",
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


@pytest.fixture
def approving_decision_maker():
    def make(request: RiskAuthorizationRequest):
        return approved_decision(
            intent_id=request.intent_id,
            strategy_id=request.strategy_id,
            session_id=request.session_id,
            signal_id=request.signal_id,
            correlation_id=request.correlation_id,
            symbol=request.symbol,
            side=request.side,
            approved_quantity=100.0,
            execution_policy="MARKET",
            decided_at=request.submitted_at,
        )

    return make


@pytest.fixture
def service(approving_decision_maker) -> AuthorizationIntegrationService:
    return AuthorizationIntegrationService(
        decision_maker=approving_decision_maker,
        clock=1000.0,
        certificate_ttl_seconds=5.0,
    )


def test_authorization_end_to_end(service):
    result = service.authorize(valid_request())
    assert result.authorized is True
    assert result.context is not None
    assert result.context.intent_id == "INT-001"
    assert result.context.approved_quantity == 100


def test_authorized_context_carries_full_identity(service):
    result = service.authorize(valid_request())
    context: Optional[AuthorizedExecutionContext] = result.context
    assert context is not None
    assert context.authorization_id == result.authorization_id
    assert context.certificate_id == result.certificate_id
    assert context.decision_id.startswith("RISK-")
    assert context.correlation_id == "CORR-001"
    assert context.strategy_id == "STRAT-001"
    assert context.session_id == "SESSION-001"
    assert context.signal_id == "SIG-001"
    assert context.symbol == "NVDA"
    assert context.side == "BUY"


def test_rejected_intent_never_reaches_execution():
    service = AuthorizationIntegrationService(
        decision_maker=lambda request: rejected_decision(
            intent_id=request.intent_id,
            correlation_id=request.correlation_id,
            reason="EXPOSURE_LIMIT",
            decided_at=request.submitted_at,
        ),
        clock=1000.0,
    )
    result = service.authorize(valid_request())
    assert result.authorized is False
    assert result.context is None
    assert result.reason == AuthorizationErrorCode.RISK_REJECTED.value


def test_duplicate_intent_is_idempotent(service):
    first = service.authorize(valid_request(intent_id="INT-001"))
    second = service.authorize(valid_request(intent_id="INT-001"))
    assert first.context is not None
    assert second.context is not None
    assert first.context.authorization_id == second.context.authorization_id
    assert first.context.certificate_id == second.context.certificate_id


def test_expired_authorization_fails_closed():
    service = AuthorizationIntegrationService(
        decision_maker=lambda request: approved_decision(
            intent_id=request.intent_id,
            strategy_id=request.strategy_id,
            session_id=request.session_id,
            signal_id=request.signal_id,
            correlation_id=request.correlation_id,
            symbol=request.symbol,
            side=request.side,
            approved_quantity=100.0,
            execution_policy="MARKET",
            decided_at=request.submitted_at,
        ),
        clock=1010.0,  # far after the 1000.0 issuance window
        certificate_ttl_seconds=5.0,
    )
    result = service.verify(
        expired_certificate(),
        approved_execution_request(),
        now=1010.0,
    )
    assert result.authorized is False
    assert result.context is None
    assert result.reason == AuthorizationErrorCode.CERTIFICATE_EXPIRED.value


def test_scope_tampering_is_blocked(service):
    certificate = approved_certificate(symbol="NVDA")
    request = approved_execution_request(symbol="AMD")
    result = service.verify(certificate, request, now=1001.0)
    assert result.authorized is False
    assert result.reason == AuthorizationErrorCode.SCOPE_MISMATCH.value


def test_quantity_escalation_is_blocked(service):
    certificate = approved_certificate(approved_quantity=100)
    request = approved_execution_request(quantity=500)
    result = service.verify(certificate, request, now=1001.0)
    assert result.authorized is False
    assert result.reason == AuthorizationErrorCode.QUANTITY_EXCEEDED.value


def test_policy_mismatch_is_blocked(service):
    certificate = approved_certificate(execution_policy="LIMIT")
    request = approved_execution_request(execution_policy="MARKET")
    result = service.verify(certificate, request, now=1001.0)
    assert result.authorized is False
    assert result.reason == AuthorizationErrorCode.POLICY_MISMATCH.value


def test_verify_success_returns_context(service):
    certificate = approved_certificate()
    result = service.verify(certificate, approved_execution_request(), now=1001.0)
    assert result.authorized is True
    assert result.context is not None
    assert result.context.approved_quantity == 100


def test_authorization_failure_is_fail_closed(service):
    class FailingIssuer(AuthorizationCertificateIssuer):
        def issue(self, decision, **kwargs):
            raise RuntimeError("issuer unavailable")

    service.issuer = FailingIssuer()
    result = service.authorize(valid_request())
    assert result.authorized is False
    assert result.context is None
    assert result.reason == AuthorizationErrorCode.INTEGRATION_FAILURE.value


def test_risk_evaluation_failure_is_fail_closed():
    def exploding_maker(request: RiskAuthorizationRequest):
        raise RuntimeError("risk engine crashed")

    service = AuthorizationIntegrationService(
        decision_maker=exploding_maker,
        clock=1000.0,
    )
    result = service.authorize(valid_request())
    assert result.authorized is False
    assert result.context is None
    assert result.reason == AuthorizationErrorCode.INTEGRATION_FAILURE.value


def test_rejected_flow_audits_requested_and_rejected(service):
    service = AuthorizationIntegrationService(
        decision_maker=lambda request: rejected_decision(
            intent_id=request.intent_id,
            correlation_id=request.correlation_id,
            reason="EXPOSURE_LIMIT",
            decided_at=request.submitted_at,
        ),
        clock=1000.0,
    )
    service.authorize(valid_request(correlation_id="CORR-REJECT"))
    records = service.audit.get_by_correlation("CORR-REJECT")
    event_types = [record.event_type.value for record in records]
    assert "REQUESTED" in event_types
    assert "REJECTED" in event_types
    assert "ISSUED" not in event_types


def test_approval_flow_audits_full_chain(service):
    service.authorize(valid_request(correlation_id="CORR-APPROVE"))
    records = service.audit.get_by_correlation("CORR-APPROVE")
    event_types = [record.event_type.value for record in records]
    assert event_types == ["REQUESTED", "APPROVED", "ISSUED"]


def test_consume_is_replay_safe(service):
    result = service.authorize(valid_request())
    assert result.context is not None
    certificate = service.issuer.certificates[
        next(iter(service.issuer.certificates))
    ]

    first = service.consume(certificate, order_request_id="OR-001", now=1001.0)
    assert first.authorized is True

    second = service.consume(certificate, order_request_id="OR-002", now=1001.0)
    assert second.authorized is False
    assert second.reason == AuthorizationErrorCode.ALREADY_CONSUMED.value


def test_verify_records_verified_audit_event(service):
    certificate = approved_certificate()
    result = service.verify(certificate, approved_execution_request(), now=1001.0)
    assert result.authorized is True
    records = service.audit.get_by_certificate(certificate.certificate_id)
    assert any(
        record.event_type.value == "VERIFIED" for record in records
    )


def approved_certificate(**overrides) -> ExecutionAuthorizationCertificate:
    defaults = dict(
        certificate_id="CERT-001",
        authorization_id="AUTH-001",
        decision_id="RISK-001",
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        approved=True,
        approved_quantity=100.0,
        issued_at=1000.0,
        expires_at=1005.0,
        symbol="NVDA",
        side="BUY",
        execution_policy="MARKET",
    )
    defaults.update(overrides)
    return ExecutionAuthorizationCertificate(**defaults)


def expired_certificate(**overrides) -> ExecutionAuthorizationCertificate:
    defaults = dict(
        certificate_id="CERT-EXPIRED",
        authorization_id="AUTH-EXPIRED",
        decision_id="RISK-EXPIRED",
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        approved=True,
        approved_quantity=100.0,
        issued_at=1000.0,
        expires_at=1005.0,
        symbol="NVDA",
        side="BUY",
        execution_policy="MARKET",
    )
    defaults.update(overrides)
    return ExecutionAuthorizationCertificate(**defaults)
