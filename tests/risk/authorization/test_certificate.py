"""Tests for the execution authorization certificate."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from typing import Optional

import pytest

from services.risk.authorization.certificate import (
    AuthorizationCertificateIssuer,
    CertificateVerifier,
    ExecutionAuthorizationCertificate,
    new_certificate_id,
)
from services.risk.authorization.decision import (
    RiskDecision,
    approved_decision,
    rejected_decision,
)


def make_decision(**overrides) -> RiskDecision:
    fields = {
        "intent_id": "INT-001",
        "strategy_id": "STRAT-001",
        "session_id": "SESSION-001",
        "signal_id": "SIG-001",
        "correlation_id": "CORR-001",
        "symbol": "NVDA",
        "side": "BUY",
        "approved_quantity": 100.0,
        "execution_policy": "LIMIT",
        "decided_at": 999.0,
        "decision_id": "RISK-001",
    }
    fields.update(overrides)
    return approved_decision(**fields)


def issue_valid_certificate(
    issuer: Optional[AuthorizationCertificateIssuer] = None,
    **overrides,
) -> ExecutionAuthorizationCertificate:
    """Issue a valid certificate; ``issued_at`` / ``expires_at`` and the
    issuing identity are popped from overrides, everything else feeds the
    decision."""
    if issuer is None:
        issuer = make_issuer()
    issued_at = float(overrides.pop("issued_at", 1000.0))
    expires_at = float(overrides.pop("expires_at", 1005.0))
    strategy_id = overrides.pop("strategy_id", "STRAT-001")
    session_id = overrides.pop("session_id", "SESSION-001")
    signal_id = overrides.pop("signal_id", "SIG-001")
    decision = make_decision(**overrides)
    return issuer.issue(
        decision,
        strategy_id=strategy_id,
        session_id=session_id,
        signal_id=signal_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def make_issuer(**kwargs) -> AuthorizationCertificateIssuer:
    return AuthorizationCertificateIssuer(**kwargs)


# --- validation ------------------------------------------------------------


def test_valid_certificate_passes_verification() -> None:
    certificate = issue_valid_certificate()
    verifier = CertificateVerifier()
    verifier.verify(
        certificate,
        intent_id="INT-001",
        correlation_id="CORR-001",
        now=1002.0,
    )


def test_expired_certificate_is_rejected() -> None:
    certificate = issue_valid_certificate(
        issued_at=1000.0,
        expires_at=1005.0,
    )
    verifier = CertificateVerifier()
    with pytest.raises(ValueError):
        verifier.verify(
            certificate,
            intent_id="INT-001",
            correlation_id="CORR-001",
            now=1006.0,
        )


def test_certificate_cannot_be_used_for_other_intent() -> None:
    certificate = issue_valid_certificate(intent_id="INT-001")
    verifier = CertificateVerifier()
    with pytest.raises(ValueError):
        verifier.verify(
            certificate,
            intent_id="INT-002",
            correlation_id="CORR-001",
            now=1001.0,
        )


def test_certificate_correlation_mismatch() -> None:
    certificate = issue_valid_certificate(correlation_id="CORR-001")
    verifier = CertificateVerifier()
    with pytest.raises(ValueError):
        verifier.verify(
            certificate,
            intent_id="INT-001",
            correlation_id="CORR-002",
            now=1001.0,
        )


def test_rejected_decision_cannot_issue_certificate() -> None:
    decision = rejected_decision(decision_id="RISK-REJ-001")
    with pytest.raises(ValueError):
        make_issuer().issue(
            decision,
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            issued_at=1000.0,
            expires_at=1005.0,
        )


def test_certificate_is_immutable() -> None:
    certificate = issue_valid_certificate()
    with pytest.raises(FrozenInstanceError):
        certificate.approved_quantity = 999.0  # type: ignore[misc]


# --- issuance rules --------------------------------------------------------


def test_issue_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValueError):
        make_issuer().issue(
            make_decision(approved_quantity=0.0),
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            issued_at=1000.0,
            expires_at=1005.0,
        )
    with pytest.raises(ValueError):
        make_issuer().issue(
            make_decision(approved_quantity=-100.0),
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            issued_at=1000.0,
            expires_at=1005.0,
        )


def test_issue_rejects_invalid_ttl() -> None:
    with pytest.raises(ValueError):
        make_issuer().issue(
            make_decision(),
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            issued_at=1005.0,
            expires_at=1000.0,
        )


def test_issue_rejects_missing_identity() -> None:
    with pytest.raises(ValueError):
        make_issuer().issue(
            make_decision(),
            strategy_id="",
            session_id="SESSION-001",
            signal_id="SIG-001",
            issued_at=1000.0,
            expires_at=1005.0,
        )


def test_issue_rejects_identity_mismatch() -> None:
    with pytest.raises(ValueError):
        make_issuer().issue(
            make_decision(strategy_id="STRAT-001"),
            strategy_id="STRAT-002",
            session_id="SESSION-001",
            signal_id="SIG-001",
            issued_at=1000.0,
            expires_at=1005.0,
        )


# --- idempotency and re-issuance -------------------------------------------


def test_issue_is_idempotent_per_decision() -> None:
    issuer = make_issuer()
    decision = make_decision()
    first = issuer.issue(
        decision,
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        issued_at=1000.0,
        expires_at=1005.0,
    )
    second = issuer.issue(
        decision,
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        issued_at=1000.0,
        expires_at=1005.0,
    )
    assert first.certificate_id == second.certificate_id
    assert len(issuer.certificates) == 1


def test_issue_reuses_valid_certificate_for_same_intent() -> None:
    issuer = make_issuer()
    first = issue_valid_certificate(issuer)
    second = issue_valid_certificate(
        issuer,
        decision_id="RISK-002",
        decided_at=1001.0,
    )
    assert first.certificate_id == second.certificate_id
    # the intent-level replay guard returns the existing certificate, so the
    # ledger still holds a single certificate for this intent
    assert len(issuer.certificates) == 1


def test_issue_allows_reissuance_after_expiry() -> None:
    issuer = make_issuer()
    first = issue_valid_certificate(
        issuer,
        issued_at=990.0,
        expires_at=1000.0,
    )
    second = issue_valid_certificate(
        issuer,
        decision_id="RISK-002",
        decided_at=1002.0,
        issued_at=1002.0,
        expires_at=1007.0,
    )
    assert first.certificate_id != second.certificate_id
    assert first.expires_at == 1000.0
    assert second.expires_at == 1007.0


def test_reissue_does_not_mutate_original() -> None:
    issuer = make_issuer()
    first = issue_valid_certificate(
        issuer,
        issued_at=990.0,
        expires_at=1000.0,
    )
    issue_valid_certificate(
        issuer,
        decision_id="RISK-002",
        decided_at=1002.0,
        issued_at=1002.0,
        expires_at=1007.0,
    )
    assert first.expires_at == 1000.0


# --- certificate identity ---------------------------------------------------


def test_certificate_carries_full_lineage() -> None:
    certificate = issue_valid_certificate()
    assert certificate.certificate_id.startswith("CERT-")
    assert certificate.authorization_id.startswith("AUTH-")
    assert certificate.decision_id == "RISK-001"
    assert certificate.intent_id == "INT-001"
    assert certificate.strategy_id == "STRAT-001"
    assert certificate.session_id == "SESSION-001"
    assert certificate.signal_id == "SIG-001"
    assert certificate.correlation_id == "CORR-001"
    assert certificate.symbol == "NVDA"
    assert certificate.side == "BUY"
    assert certificate.execution_policy == "LIMIT"
    assert certificate.approved_quantity == 100.0


def test_verify_rejects_missing_approved_quantity() -> None:
    certificate = ExecutionAuthorizationCertificate(
        certificate_id="CERT-001",
        authorization_id="AUTH-001",
        decision_id="RISK-001",
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        approved=True,
        approved_quantity=None,
        issued_at=1000.0,
        expires_at=1005.0,
    )
    verifier = CertificateVerifier()
    with pytest.raises(ValueError):
        verifier.verify(
            certificate,
            intent_id="INT-001",
            correlation_id="CORR-001",
            now=1001.0,
        )


def test_verify_rejects_non_positive_quantity() -> None:
    certificate = ExecutionAuthorizationCertificate(
        certificate_id="CERT-001",
        authorization_id="AUTH-001",
        decision_id="RISK-001",
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        approved=True,
        approved_quantity=0.0,
        issued_at=1000.0,
        expires_at=1005.0,
    )
    verifier = CertificateVerifier()
    with pytest.raises(ValueError):
        verifier.verify(
            certificate,
            intent_id="INT-001",
            correlation_id="CORR-001",
            now=1001.0,
        )


def test_new_certificate_id_shape() -> None:
    certificate_id = new_certificate_id(1775000000.0)
    date_part = datetime.fromtimestamp(1775000000.0).strftime("%Y%m%d")
    assert certificate_id.startswith(f"CERT-{date_part}-")
