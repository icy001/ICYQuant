"""Tests for execution eligibility and authorization replay protection."""

from typing import Optional

import pytest

from services.risk.authorization.certificate import ExecutionAuthorizationCertificate
from services.risk.authorization.scope import AuthorizationScope
from services.risk.authorization.validator import (
    AuthorizationViolation,
    ExecutionEligibilityValidator,
    ExecutionRequest,
)


def make_validator(**kwargs) -> ExecutionEligibilityValidator:
    fields = {"clock": 1001.0}
    fields.update(kwargs)
    return ExecutionEligibilityValidator(**fields)


def valid_certificate(**overrides) -> ExecutionAuthorizationCertificate:
    fields = {
        "certificate_id": "CERT-001",
        "authorization_id": "AUTH-001",
        "decision_id": "RISK-001",
        "intent_id": "INT-001",
        "strategy_id": "STRAT-001",
        "session_id": "SESSION-001",
        "signal_id": "SIG-001",
        "correlation_id": "CORR-001",
        "approved": True,
        "approved_quantity": 100.0,
        "issued_at": 1000.0,
        "expires_at": 1005.0,
        "symbol": "NVDA",
        "side": "BUY",
        "execution_policy": "LIMIT",
    }
    fields.update(overrides)
    return ExecutionAuthorizationCertificate(**fields)


def expired_certificate() -> ExecutionAuthorizationCertificate:
    return valid_certificate(expires_at=500.0)


def execution_request(**overrides) -> ExecutionRequest:
    fields = {
        "intent_id": "INT-001",
        "strategy_id": "STRAT-001",
        "session_id": "SESSION-001",
        "signal_id": "SIG-001",
        "correlation_id": "CORR-001",
        "symbol": "NVDA",
        "side": "BUY",
        "quantity": 100.0,
        "execution_policy": "LIMIT",
        "idempotency_key": "OR-001",
    }
    fields.update(overrides)
    return ExecutionRequest(**fields)


def consume_authorization(
    certificate: ExecutionAuthorizationCertificate,
    *,
    order_request_id: str,
    validator: Optional[ExecutionEligibilityValidator] = None,
):
    validator = validator if validator is not None else make_validator()
    return validator.consume(certificate, order_request_id=order_request_id)


# --- eligibility -----------------------------------------------------------


def test_matching_scope_is_eligible() -> None:
    certificate = valid_certificate(
        intent_id="INT-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
    )
    request = execution_request(
        intent_id="INT-001",
        symbol="NVDA",
        side="BUY",
        quantity=100.0,
    )
    result = make_validator().validate(certificate, request)
    assert result.eligible is True
    assert result.reason is None


def test_quantity_cannot_exceed_authorization() -> None:
    certificate = valid_certificate(approved_quantity=100.0)
    request = execution_request(quantity=101.0)
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.QUANTITY_EXCEEDS_AUTHORIZATION.value


def test_symbol_mismatch_is_rejected() -> None:
    certificate = valid_certificate(symbol="NVDA")
    request = execution_request(symbol="AMD")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.SYMBOL_MISMATCH.value


def test_side_mismatch_is_rejected() -> None:
    certificate = valid_certificate(side="BUY")
    request = execution_request(side="SELL")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.SIDE_MISMATCH.value


def test_intent_mismatch_is_rejected() -> None:
    certificate = valid_certificate(intent_id="INT-001")
    request = execution_request(intent_id="INT-002")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.INTENT_MISMATCH.value


def test_strategy_mismatch_is_rejected() -> None:
    certificate = valid_certificate(strategy_id="STRAT-001")
    request = execution_request(strategy_id="STRAT-002")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.STRATEGY_MISMATCH.value


def test_session_mismatch_is_rejected() -> None:
    certificate = valid_certificate(session_id="SESSION-001")
    request = execution_request(session_id="SESSION-002")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.SESSION_MISMATCH.value


def test_signal_mismatch_is_rejected() -> None:
    certificate = valid_certificate(signal_id="SIG-001")
    request = execution_request(signal_id="SIG-002")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.SIGNAL_MISMATCH.value


def test_policy_mismatch_is_rejected() -> None:
    certificate = valid_certificate(execution_policy="LIMIT")
    request = execution_request(execution_policy="MARKET")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.POLICY_MISMATCH.value


def test_correlation_mismatch_is_rejected() -> None:
    certificate = valid_certificate(correlation_id="CORR-001")
    request = execution_request(correlation_id="CORR-002")
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.CORRELATION_MISMATCH.value


def test_expired_certificate_is_not_eligible() -> None:
    certificate = expired_certificate()
    request = execution_request()
    result = make_validator().validate(certificate, request)
    assert result.eligible is False
    assert result.reason == AuthorizationViolation.CERTIFICATE_EXPIRED.value


def test_unapproved_certificate_is_not_eligible() -> None:
    certificate = valid_certificate(approved=False)
    request = execution_request()
    result = make_validator().validate(certificate, request)
    assert result.eligible is False


def test_eligible_result_carries_certificate_identity() -> None:
    result = make_validator().validate(
        valid_certificate(certificate_id="CERT-001", authorization_id="AUTH-001"),
        execution_request(),
    )
    assert result.eligible is True
    assert result.authorization_id == "AUTH-001"
    assert result.certificate_id == "CERT-001"


def test_validator_exposes_scope() -> None:
    validator = make_validator()
    scope = validator.scope(valid_certificate())
    assert isinstance(scope, AuthorizationScope)
    assert scope.intent_id == "INT-001"
    assert scope.symbol == "NVDA"
    assert scope.approved_quantity == 100.0


# --- replay protection ------------------------------------------------------


def test_authorization_replay_is_blocked() -> None:
    validator = make_validator()
    certificate = valid_certificate()
    first = consume_authorization(
        certificate,
        order_request_id="OR-001",
        validator=validator,
    )
    second = consume_authorization(
        certificate,
        order_request_id="OR-002",
        validator=validator,
    )
    assert first.accepted is True
    assert second.accepted is False
    assert second.reason == "authorization_already_consumed"


def test_replay_same_order_request_is_idempotent() -> None:
    validator = make_validator()
    certificate = valid_certificate()
    first = consume_authorization(
        certificate,
        order_request_id="OR-001",
        validator=validator,
    )
    second = consume_authorization(
        certificate,
        order_request_id="OR-001",
        validator=validator,
    )
    assert first.accepted is True
    assert second.accepted is True
    assert second is first


def test_consume_requires_order_request_id() -> None:
    validator = make_validator()
    with pytest.raises(ValueError):
        validator.consume(valid_certificate(), order_request_id="")
