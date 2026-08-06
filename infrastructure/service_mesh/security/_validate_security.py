"""Validation tests for ICYQuant Service Mesh Security.

Runs comprehensive validation across all security components and
reports pass/fail counts.
"""

import asyncio
import sys
import traceback
from typing import Any, Dict, List

# Ensure project root is in path
sys.path.insert(0, ".")

PASSED = 0
FAILED = 0
FAILURES: List[str] = []


def check(condition: bool, name: str) -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        FAILURES.append(f"  - FAIL: {name}")


def report_section(title: str) -> None:
    print(f"\n=== {title} ===")


# ============================================================
# 1. Exceptions
# ============================================================
async def test_exceptions() -> None:
    report_section("1. Security Exceptions")
    from infrastructure.service_mesh.security import (
        SecurityError, IdentityError, WorkloadIdentityError,
        TrustDomainError, SPIFFEError, CertificateError,
        CertificateIssueError, CertificateValidationError,
        CertificateRevocationError, CertificateRotationError,
        CertificateExpiredError, MTLSError, HandshakeError,
        AuthenticationError, AuthorizationError, PolicyError,
        PolicyNotFoundError, KeyError_, SecretError, TokenError,
        AuditError, SecurityManagerError,
    )

    base = SecurityError("base error")
    check(str(base) == "base error", "SecurityError message")
    check(isinstance(IdentityError(), SecurityError), "IdentityError subclass")
    check(
        issubclass(WorkloadIdentityError, IdentityError),
        "WorkloadIdentityError subclass",
    )
    check(
        issubclass(CertificateIssueError, CertificateError),
        "CertificateIssueError subclass",
    )
    check(
        issubclass(HandshakeError, MTLSError),
        "HandshakeError subclass",
    )
    check(
        issubclass(PolicyNotFoundError, PolicyError),
        "PolicyNotFoundError subclass",
    )
    check(
        issubclass(SecurityManagerError, SecurityError),
        "SecurityManagerError subclass",
    )
    # Verify details field
    err = SecurityError("with details", {"key": "value"})
    check(err.details == {"key": "value"}, "SecurityError details")


# ============================================================
# 2. SecurityMetrics
# ============================================================
async def test_metrics() -> None:
    report_section("2. SecurityMetrics")
    from infrastructure.service_mesh.security import SecurityMetrics

    m = SecurityMetrics()
    m.increment_auth({"method": "certificate"})
    m.increment_authorization({"resource": "orders"})
    m.increment_certificate_issue({"spiffe_id": "spiffe://x"})
    m.increment_certificate_rotation()
    m.increment_mtls_handshake()
    m.increment_denied({"reason": "auth_failed"})
    m.increment_audit()
    m.increment_identity({"service": "oms"})
    m.set_active_certificates(10)

    s = m.get_summary()
    check(
        s["counters"]["icyquant_security_auth_total"] == 1,
        "auth counter",
    )
    check(
        s["counters"]["icyquant_security_authorization_total"] == 1,
        "authorization counter",
    )
    check(
        s["counters"]["icyquant_certificate_issue_total"] == 1,
        "certificate issue counter",
    )
    check(
        s["counters"]["icyquant_certificate_rotation_total"] == 1,
        "certificate rotation counter",
    )
    check(
        s["counters"]["icyquant_mtls_handshake_total"] == 1,
        "mtls handshake counter",
    )
    check(
        s["counters"]["icyquant_security_denied_total"] == 1,
        "denied counter",
    )
    check(
        s["counters"]["icyquant_security_audit_total"] == 1,
        "audit counter",
    )
    check(
        s["counters"]["icyquant_security_identity_total"] == 1,
        "identity counter",
    )
    check(
        s["gauges"]["icyquant_certificate_active"] == 10.0,
        "active certificates gauge",
    )

    m.reset()
    s2 = m.get_summary()
    check(
        s2["counters"]["icyquant_security_auth_total"] == 0,
        "reset works",
    )


# ============================================================
# 3. SecurityTelemetry
# ============================================================
async def test_telemetry() -> None:
    report_section("3. SecurityTelemetry")
    from infrastructure.service_mesh.security import SecurityTelemetry

    t = SecurityTelemetry()
    t.log_authentication("spiffe://icyquant.local/oms/svc", "certificate", True)
    t.log_authorization("spiffe://icyquant.local/oms/svc", "orders", "access", True, "pol-1")
    t.log_certificate_event("issued", "cert-001")
    t.log_mtls_handshake("client-x", "server-y", True, 0.05)
    t.log_policy_evaluation("pol-1", "spiffe://x", "allowed")
    t.log_security_event("initialized", "security_manager")

    events = t.get_events()
    check(len(events) == 6, "6 events logged")
    check(len(t.get_events("authentication")) == 1, "auth event filter")
    check(len(t.get_events("authorization")) == 1, "authz event filter")
    check(len(t.get_events("certificate")) == 1, "cert event filter")
    check(len(t.get_events("mtls_handshake")) == 1, "mtls event filter")
    check(len(t.get_events("policy_evaluation")) == 1, "policy event filter")
    check(len(t.get_events("security_event")) == 1, "security event filter")

    stats = t.get_stats()
    check(stats["event_count"] == 6, "event count stats")

    t.clear()
    check(len(t.get_events()) == 0, "telemetry cleared")


# ============================================================
# 4. SecurityAudit
# ============================================================
async def test_audit() -> None:
    report_section("4. SecurityAudit")
    from infrastructure.service_mesh.security import (
        SecurityAudit, AuditEventType, AuditSeverity,
    )

    audit = SecurityAudit()
    audit.record_authentication(
        principal="spiffe://icyquant.local/oms/svc",
        success=True,
        method="certificate",
    )
    audit.record_authorization(
        principal="spiffe://icyquant.local/oms/svc",
        resource="orders",
        allowed=True,
        policy_id="pol-1",
    )
    audit.record_certificate_issue(
        cert_id="cert-001",
        principal="spiffe://icyquant.local/oms/svc",
        ca_id="icyquant-ca",
    )
    audit.record_certificate_revoke("cert-001", "key_compromise")
    audit.record_certificate_rotate("cert-002", "cert-001")
    audit.record_policy_change("pol-1", "registered")
    audit.record_security_incident("intrusion attempt", AuditSeverity.CRITICAL)

    records = audit.get_records()
    check(len(records) == 7, "7 audit records")
    check(
        len(audit.get_records(event_type=AuditEventType.AUTHENTICATION)) == 1,
        "auth record filter",
    )
    check(
        len(audit.get_records(event_type=AuditEventType.CERTIFICATE_ISSUE)) == 1,
        "cert issue filter",
    )
    check(
        len(audit.get_records(severity=AuditSeverity.CRITICAL)) == 1,
        "critical severity filter",
    )
    check(
        len(audit.get_records(severity=AuditSeverity.WARNING)) >= 2,
        "warning severity filter",
    )

    # Listener notification
    received = []
    audit.subscribe(lambda r: received.append(r))
    audit.record("test_event", actor="system")
    check(len(received) == 1, "listener notified")

    stats = audit.get_stats()
    check(stats["record_count"] == 8, "record count stats")
    check(stats["listener_count"] == 1, "listener count stats")


# ============================================================
# 5. SecurityDiagnostics
# ============================================================
async def test_diagnostics() -> None:
    report_section("5. SecurityDiagnostics")
    from infrastructure.service_mesh.security import SecurityDiagnostics

    d = SecurityDiagnostics()
    d.register_identity("id-1", {"spiffe_id": "spiffe://x/oms/svc"})
    d.register_identity("id-2", {"spiffe_id": "spiffe://x/risk/svc"})
    d.register_certificate("cert-1", {"spiffe_id": "spiffe://x/oms/svc"})
    d.register_mtls_session("sess-1", {"client": "spiffe://x/oms/svc"})

    snap = d.get_snapshot()
    check(snap["identity_count"] == 2, "identity count")
    check(snap["certificate_count"] == 1, "certificate count")
    check(snap["mtls_session_count"] == 1, "mtls session count")

    d.record_policy_evaluation("pol-1", "spiffe://x", "allowed")
    snap2 = d.get_snapshot()
    check(snap2["policy_evaluation_count"] == 1, "policy eval count")

    d.unregister_identity("id-1")
    check(
        d.get_snapshot()["identity_count"] == 1,
        "identity unregistered",
    )

    d.clear()
    check(d.get_snapshot()["identity_count"] == 0, "diagnostics cleared")


# ============================================================
# 6. Identity & IdentityService
# ============================================================
async def test_identity() -> None:
    report_section("6. Identity & IdentityService")
    from infrastructure.service_mesh.security import (
        Identity, IdentityService, IdentityStatus,
    )

    identity = Identity(
        identity_id="id-1",
        spiffe_id="spiffe://icyquant.local/oms/order-service",
        trust_domain="icyquant.local",
        namespace="oms",
        service_name="order-service",
        status=IdentityStatus.ACTIVE,
    )
    check(identity.is_active, "identity active")
    check(identity.is_valid, "identity valid")
    check(
        identity.to_dict()["spiffe_id"] == "spiffe://icyquant.local/oms/order-service",
        "identity dict",
    )

    svc = IdentityService()
    svc.register(identity)
    check(
        svc.get_identity("id-1") is identity,
        "identity retrieved by id",
    )
    check(
        svc.get_by_spiffe_id("spiffe://icyquant.local/oms/order-service") is identity,
        "identity retrieved by spiffe",
    )
    check(len(svc.list_identities()) == 1, "list identities")
    check(
        len(svc.list_identities(namespace="oms")) == 1,
        "list by namespace",
    )
    check(svc.validate_identity("spiffe://icyquant.local/oms/order-service"), "validate identity")
    check(not svc.validate_identity("spiffe://unknown/x"), "unknown identity invalid")

    svc.suspend("id-1")
    check(not identity.is_active, "identity suspended")
    svc.activate("id-1")
    check(identity.is_active, "identity activated")
    svc.revoke("id-1")
    check(not identity.is_active, "identity revoked")

    stats = svc.get_stats()
    check(stats["total_identities"] == 1, "identity stats total")


# ============================================================
# 7. WorkloadIdentity
# ============================================================
async def test_workload_identity() -> None:
    report_section("7. WorkloadIdentity")
    from infrastructure.service_mesh.security import (
        WorkloadIdentity, WorkloadIdentityManager,
    )

    wi = WorkloadIdentity(
        trust_domain="icyquant.local",
        namespace="execution",
        service_name="order-service",
        instance_id="pod-1234",
        ttl_seconds=3600,
    )
    check(
        wi.spiffe_id == "spiffe://icyquant.local/execution/order-service/pod-1234",
        "spiffe id format",
    )
    check(len(wi.identity_id) == 16, "identity id length")
    check(not wi.is_expired, "workload identity not expired")

    mgr = WorkloadIdentityManager()
    created = mgr.create_identity(
        service_name="risk-engine",
        namespace="risk",
        trust_domain="icyquant.local",
        instance_id="inst-1",
        ttl_seconds=7200,
    )
    check(
        created.spiffe_id == "spiffe://icyquant.local/risk/risk-engine/inst-1",
        "created workload spiffe id",
    )
    check(
        mgr.get_identity(created.identity_id) is created,
        "workload retrieved",
    )
    check(
        mgr.get_by_spiffe_id(created.spiffe_id) is created,
        "workload retrieved by spiffe",
    )
    check(len(mgr.list_identities()) == 1, "list workloads")
    check(
        len(mgr.list_identities(namespace="risk")) == 1,
        "list by namespace",
    )

    refreshed = mgr.refresh_identity(created.identity_id, 3600)
    check(refreshed is not None, "workload refreshed")
    check(mgr.revoke_identity(created.identity_id), "workload revoked")
    check(
        mgr.get_identity(created.identity_id) is None,
        "workload removed after revoke",
    )


# ============================================================
# 8. TrustDomain
# ============================================================
async def test_trust_domain() -> None:
    report_section("8. TrustDomain")
    from infrastructure.service_mesh.security import (
        TrustDomain, TrustDomainManager, TrustDomainLevel,
    )

    td = TrustDomain(
        name="icyquant.local",
        level=TrustDomainLevel.PRODUCTION,
    )
    check(td.is_enabled, "trust domain enabled")
    check(td.accepts_identity_from("icyquant.local"), "accepts own identities")
    check(
        not td.accepts_identity_from("other.domain"),
        "denies cross-domain by default",
    )

    td.add_federation("staging.icyquant.local")
    check(td.is_federated("staging.icyquant.local"), "federation added")
    td.allow_cross_domain = True
    check(
        td.accepts_identity_from("staging.icyquant.local"),
        "accepts federated identities",
    )
    check(td.remove_federation("staging.icyquant.local"), "federation removed")

    mgr = TrustDomainManager(td)
    check(mgr.get_domain("icyquant.local") is td, "domain retrieved")
    check(len(mgr.list_domains()) == 1, "list domains")
    check(
        mgr.validate_trust("icyquant.local", "icyquant.local"),
        "validate same trust",
    )
    check(
        not mgr.validate_trust("unknown", "icyquant.local"),
        "validate unknown source",
    )

    staging = TrustDomain(name="staging.local", level=TrustDomainLevel.STAGING)
    mgr.register(staging)
    mgr.add_federation("icyquant.local", "staging.local")
    check(
        mgr.get_domain("icyquant.local").is_federated("staging.local"),
        "bidirectional federation",
    )


# ============================================================
# 9. SPIFFE
# ============================================================
async def test_spiffe() -> None:
    report_section("9. SPIFFE")
    from infrastructure.service_mesh.security import (
        SPIFFEID, SPIFFEBundle, SPIFFEManager, SPIFFEError,
    )

    sid = SPIFFEID.build(
        trust_domain="icyquant.local",
        namespace="oms",
        service="order-service",
        instance="pod-1",
    )
    check(
        sid.uri == "spiffe://icyquant.local/oms/order-service/pod-1",
        "spiffe id built",
    )
    check(str(sid) == sid.uri, "spiffe str representation")
    check(sid == "spiffe://icyquant.local/oms/order-service/pod-1", "spiffe equality")

    parsed = SPIFFEID.parse("spiffe://icyquant.local/risk/risk-engine")
    check(parsed.trust_domain == "icyquant.local", "parsed trust domain")
    check(parsed.path == "/risk/risk-engine", "parsed path")

    try:
        SPIFFEID.parse("invalid-uri")
        check(False, "invalid spiffe should raise")
    except SPIFFEError:
        check(True, "invalid spiffe raises")

    bundle = SPIFFEBundle(trust_domain="icyquant.local")
    bundle.add_key("key-1", "public-key-data")
    bundle.add_key("key-2", "public-key-data-2")
    check(bundle.list_keys()["key-1"] == "public-key-data", "bundle key")
    check(len(bundle.list_keys()) == 2, "bundle key count")
    check(bundle.remove_key("key-1"), "bundle key removed")

    mgr = SPIFFEManager()
    created = mgr.create_id("icyquant.local", "oms", "svc", "inst")
    check(isinstance(created, SPIFFEID), "manager creates id")
    check(mgr.validate_id("spiffe://icyquant.local/x/y"), "validate id")
    check(not mgr.validate_id("invalid"), "invalid id")
    mgr.register_bundle(bundle)
    check(mgr.verify_trust(sid), "verify trust")


# ============================================================
# 10. CertificateAuthority
# ============================================================
async def test_certificate_authority() -> None:
    report_section("10. CertificateAuthority")
    from infrastructure.service_mesh.security import (
        CertificateAuthority, CertificateRecord, CertificateType,
    )

    ca = CertificateAuthority(ca_id="test-ca", trust_domain="icyquant.local")
    check(ca.ca_id == "test-ca", "ca id")
    check(not ca.is_running, "ca not running initially")
    ca.start()
    check(ca.is_running, "ca started")

    cert = await ca.issue(
        spiffe_id="spiffe://icyquant.local/oms/svc",
        cert_type=CertificateType.WORKLOAD,
        ttl_hours=24,
    )
    check(cert.cert_id.startswith("cert-"), "cert id format")
    check(cert.spiffe_id == "spiffe://icyquant.local/oms/svc", "cert spiffe")
    check(cert.issuer == "test-ca", "cert issuer")
    check(cert.is_active, "cert active")
    check(not cert.is_expired, "cert not expired")
    check(not cert.is_revoked, "cert not revoked")

    check(
        ca.get_certificate(cert.cert_id) is cert,
        "cert retrieved",
    )
    check(
        len(ca.get_by_spiffe_id("spiffe://icyquant.local/oms/svc")) == 1,
        "cert by spiffe",
    )
    check(len(ca.list_certificates()) == 1, "list certificates")
    check(
        len(ca.list_certificates(status="active")) == 1,
        "list active certificates",
    )

    # Revocation
    result = await ca.revoke(cert.cert_id, "testing")
    check(result, "cert revoked")
    check(cert.is_revoked, "cert is revoked")

    # Rotation
    cert2 = await ca.issue(
        spiffe_id="spiffe://icyquant.local/oms/svc2",
        cert_type=CertificateType.WORKLOAD,
    )
    new_cert = await ca.rotate(cert2.cert_id)
    check(new_cert.cert_id != cert2.cert_id, "rotated cert new id")
    check(cert2.is_revoked, "old cert revoked after rotation")

    stats = ca.get_stats()
    check(stats["ca_id"] == "test-ca", "ca stats id")
    check(stats["issue_count"] == 3, "ca stats issue count")
    check(stats["revoke_count"] == 2, "ca stats revoke count")


# ============================================================
# 11. CertificateStore
# ============================================================
async def test_certificate_store() -> None:
    report_section("11. CertificateStore")
    from infrastructure.service_mesh.security import (
        CertificateStore, CertificateRecord,
    )
    from datetime import datetime, timedelta

    store = CertificateStore()
    cert = CertificateRecord(
        cert_id="cert-1",
        spiffe_id="spiffe://icyquant.local/oms/svc",
    )
    store.store(cert)
    check(store.get("cert-1") is cert, "cert retrieved from store")
    check(
        len(store.get_by_spiffe_id("spiffe://icyquant.local/oms/svc")) == 1,
        "cert by spiffe",
    )
    check(len(store.list_all()) == 1, "list all")
    check(len(store.list_active()) == 1, "list active")

    # Expired cert
    expired = CertificateRecord(
        cert_id="cert-exp",
        spiffe_id="spiffe://icyquant.local/oms/exp",
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    store.store(expired)
    check(len(store.list_active()) == 1, "expired not in active")
    check(store.remove("cert-1"), "cert removed")
    check(store.get("cert-1") is None, "cert gone after remove")

    stats = store.get_stats()
    check(stats["total"] == 1, "store stats total")


# ============================================================
# 12. CertificateManager
# ============================================================
async def test_certificate_manager() -> None:
    report_section("12. CertificateManager")
    from infrastructure.service_mesh.security import CertificateManager

    mgr = CertificateManager()
    check(not mgr.is_running, "not running initially")
    mgr.start()
    check(mgr.is_running, "started")

    cert = await mgr.issue(
        spiffe_id="spiffe://icyquant.local/oms/svc",
        ttl_hours=24,
    )
    check(cert.cert_id, "cert issued id")
    check(
        mgr.get_certificate(cert.cert_id) is cert,
        "cert retrieved",
    )
    check(len(mgr.list_certificates()) == 1, "list certificates")

    # Validate
    result = mgr.validate(cert.cert_id)
    check(result["valid"], "cert valid")
    check(result["reason"] == "ok", "cert valid reason")

    # Renew
    old_expiry = cert.expires_at
    renewed = await mgr.renew(cert.cert_id, ttl_hours=48)
    check(renewed.expires_at > old_expiry, "cert renewed extends expiry")

    # Revoke
    revoked = await mgr.revoke(cert.cert_id, "testing")
    check(revoked, "cert revoked")
    result2 = mgr.validate(cert.cert_id)
    check(not result2["valid"], "revoked cert invalid")
    check(result2["reason"] == "revoked", "revoked reason")

    # Expiring soon
    expiring = await mgr.issue(
        spiffe_id="spiffe://icyquant.local/risk/svc",
        ttl_hours=2,
    )
    check(len(mgr.get_expiring_soon(hours=3)) >= 1, "expiring soon")

    stats = mgr.get_stats()
    check(stats["issue_count"] == 2, "manager issue count")
    check(stats["revoke_count"] == 1, "manager revoke count")
    mgr.stop()
    check(not mgr.is_running, "manager stopped")


# ============================================================
# 13. CertificateValidator
# ============================================================
async def test_certificate_validator() -> None:
    report_section("13. CertificateValidator")
    from infrastructure.service_mesh.security import (
        CertificateValidator, CertificateRecord,
    )
    from datetime import datetime, timedelta

    validator = CertificateValidator()
    validator.add_trusted_issuer("icyquant-ca")
    check("icyquant-ca" in validator.trusted_issuers, "trusted issuer added")

    cert = CertificateRecord(
        cert_id="cert-1",
        spiffe_id="spiffe://icyquant.local/oms/svc",
        issuer="icyquant-ca",
        public_key="pub-key",
    )
    result = validator.validate(cert)
    check(result.valid, "valid cert")
    check(result.checks["signature"], "signature check")
    check(result.checks["expiration"], "expiration check")
    check(result.checks["issuer"], "issuer check")
    check(result.checks["trust_chain"], "trust chain check")
    check(result.checks["revocation"], "revocation check")

    # Expired cert
    expired = CertificateRecord(
        cert_id="cert-exp",
        spiffe_id="spiffe://icyquant.local/oms/exp",
        issuer="icyquant-ca",
        public_key="pub-key",
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    result2 = validator.validate(expired)
    check(not result2.valid, "expired cert invalid")
    check(not result2.checks["expiration"], "expiration check failed")

    # Untrusted issuer
    untrusted = CertificateRecord(
        cert_id="cert-un",
        spiffe_id="spiffe://icyquant.local/oms/un",
        issuer="unknown-ca",
        public_key="pub-key",
    )
    result3 = validator.validate(untrusted)
    check(not result3.valid, "untrusted issuer invalid")
    check(not result3.checks["issuer"], "issuer check failed")

    # Batch validation
    results = validator.validate_batch([cert, expired, untrusted])
    check(len(results) == 3, "batch validation count")

    stats = validator.get_stats()
    check(stats["validation_count"] == 6, "validation count stats")
    check(stats["failure_count"] == 4, "failure count stats")


# ============================================================
# 14. RevocationManager
# ============================================================
async def test_revocation() -> None:
    report_section("14. RevocationManager")
    from infrastructure.service_mesh.security import (
        RevocationManager, RevocationReason,
    )

    mgr = RevocationManager()
    entry = mgr.revoke(
        cert_id="cert-1",
        serial_number="serial-001",
        reason=RevocationReason.KEY_COMPROMISE,
        revoked_by="admin",
    )
    check(entry.cert_id == "cert-1", "revoked cert id")
    check(entry.reason == RevocationReason.KEY_COMPROMISE, "revocation reason")
    check(mgr.is_revoked("cert-1"), "cert is revoked")
    check(
        mgr.is_revoked_by_serial("serial-001"),
        "cert is revoked by serial",
    )
    check(
        mgr.get_revocation_entry("cert-1") is entry,
        "revocation entry retrieved",
    )

    crl = mgr.get_crl()
    check(crl["count"] == 1, "crl count")
    check(len(crl["entries"]) == 1, "crl entries")

    # Listener
    received = []
    mgr.subscribe(lambda event, data: received.append((event, data)))
    mgr.revoke("cert-2", reason=RevocationReason.EXPIRED)
    check(len(received) == 1, "listener notified")
    check(received[0][0] == "revoke", "listener event type")

    # Unrevoke
    check(mgr.unrevoke("cert-1"), "cert unrevoked")
    check(not mgr.is_revoked("cert-1"), "cert no longer revoked")

    stats = mgr.get_stats()
    check(stats["revoked_count"] == 1, "revoked count stats")


# ============================================================
# 15. CertificateRotator
# ============================================================
async def test_certificate_rotator() -> None:
    report_section("15. CertificateRotator")
    from infrastructure.service_mesh.security import (
        CertificateRotator, CertificateManager, RotationType,
    )

    cert_mgr = CertificateManager()
    cert_mgr.start()

    rotator = CertificateRotator(
        cert_manager=cert_mgr,
        rotation_interval_s=60,
        renewal_threshold_hours=1,
    )
    check(not rotator.is_running, "rotator not running")

    # Issue a cert that expires soon
    short_cert = await cert_mgr.issue(
        spiffe_id="spiffe://icyquant.local/oms/short",
        ttl_hours=1,
    )
    result = await rotator.scheduled_rotation()
    check(result["type"] == RotationType.SCHEDULED, "scheduled type")
    check(len(result["rotated"]) == 1, "cert rotated scheduled")
    check(result["count"] == 1, "scheduled rotation count")

    # Emergency rotation
    cert2 = await cert_mgr.issue(
        spiffe_id="spiffe://icyquant.local/oms/cert2",
        ttl_hours=24,
    )
    emergency = await rotator.emergency_rotation(cert2.cert_id, "compromise")
    check(emergency["type"] == RotationType.EMERGENCY, "emergency type")
    check(emergency["old_cert_id"] == cert2.cert_id, "emergency old cert")

    # Rolling rotation
    certs = []
    for i in range(3):
        c = await cert_mgr.issue(
            spiffe_id=f"spiffe://icyquant.local/oms/cert{i}",
            ttl_hours=24,
        )
        certs.append(c.cert_id)
    rolling = await rotator.rolling_rotation(certs)
    check(rolling["type"] == RotationType.ROLLING, "rolling type")
    check(rolling["count"] == 3, "rolling count")

    stats = rotator.get_stats()
    check(stats["rotation_count"] == 5, "rotation count stats")
    check(stats["emergency_count"] == 1, "emergency count stats")
    check(stats["rolling_count"] == 3, "rolling count stats")


# ============================================================
# 16. KeyManager
# ============================================================
async def test_key_manager() -> None:
    report_section("16. KeyManager")
    from infrastructure.service_mesh.security import KeyManager, KeyType

    km = KeyManager()
    key = km.create_key(
        key_type=KeyType.PRIVATE,
        algorithm="RSA-2048",
        owner="oms-service",
        ttl_hours=72,
    )
    check(key.key_id.startswith("key-"), "key id format")
    check(key.key_type == KeyType.PRIVATE, "key type")
    check(key.algorithm == "RSA-2048", "key algorithm")
    check(key.owner == "oms-service", "key owner")
    check(not key.is_expired, "key not expired")

    check(km.get_key(key.key_id) is key, "key retrieved")
    check(len(km.list_keys()) == 1, "list keys")
    check(
        len(km.list_keys(key_type=KeyType.PRIVATE)) == 1,
        "list by type",
    )

    # Rotation
    new_key = km.rotate_key(key.key_id)
    check(new_key is not None, "key rotated")
    check(new_key.key_id != key.key_id, "new key id")
    check(key.rotated, "old key marked rotated")
    check(key.rotation_count == 1, "old key rotation count")

    stats = km.get_stats()
    check(stats["create_count"] == 2, "create count stats")
    check(stats["rotate_count"] == 1, "rotate count stats")

    check(km.delete_key(key.key_id), "key deleted")
    check(km.get_key(key.key_id) is None, "key gone")


# ============================================================
# 17. SecretProvider
# ============================================================
async def test_secret_provider() -> None:
    report_section("17. SecretProvider")
    from infrastructure.service_mesh.security import (
        SecretProvider, SecretError,
    )

    sp = SecretProvider()
    check(not sp.is_running, "not running")
    sp.start()
    check(sp.is_running, "started")

    secret = sp.store(
        secret_id="tls-key-1",
        secret_type="tls_key",
        value="secret-data",
        metadata={"service": "oms"},
    )
    check(secret.secret_id == "tls-key-1", "secret id")
    check(secret.secret_type == "tls_key", "secret type")
    check(sp.get("tls-key-1") == "secret-data", "secret value retrieved")
    check(sp.get_record("tls-key-1").access_count == 1, "access count")

    try:
        sp.get("missing")
        check(False, "missing secret should raise")
    except SecretError:
        check(True, "missing secret raises")

    check(sp.remove("tls-key-1"), "secret removed")
    check(sp.get_record("tls-key-1") is None, "secret gone")

    stats = sp.get_stats()
    check(stats["access_count"] == 2, "access count stats")
    sp.stop()


# ============================================================
# 18. TokenProvider
# ============================================================
async def test_token_provider() -> None:
    report_section("18. TokenProvider")
    from infrastructure.service_mesh.security import TokenProvider

    tp = TokenProvider()
    record = tp.issue_token(
        principal="spiffe://icyquant.local/oms/svc",
        token_type="mesh",
        ttl_seconds=3600,
        claims={"role": "admin"},
    )
    check(len(record.token) == 64, "token length")
    check(record.principal == "spiffe://icyquant.local/oms/svc", "token principal")
    check(record.token_type == "mesh", "token type")
    check(record.is_valid, "token valid")

    check(tp.validate_token(record.token), "token validated")
    check(not tp.validate_token("invalid-token"), "invalid token")
    check(
        tp.get_token(record.token) is record,
        "token retrieved",
    )
    check(tp.revoke_token(record.token), "token revoked")
    check(not tp.validate_token(record.token), "revoked token invalid")

    stats = tp.get_stats()
    check(stats["issue_count"] == 1, "issue count stats")
    check(stats["validation_count"] == 3, "validation count stats")


# ============================================================
# 19. HandshakeManager
# ============================================================
async def test_handshake() -> None:
    report_section("19. HandshakeManager")
    from infrastructure.service_mesh.security import (
        HandshakeManager, HandshakeState,
    )

    hm = HandshakeManager()
    # Handshake without certs (no validation errors)
    session = await hm.perform_handshake(
        client_identity="spiffe://icyquant.local/oms/client",
        server_identity="spiffe://icyquant.local/oms/server",
    )
    check(session.state == HandshakeState.ESTABLISHED, "handshake established")
    check(session.session_key, "session key present")
    check(session.cipher_suite, "cipher suite present")
    check(session.completed_at is not None, "completed timestamp")
    check(len(session.errors) == 0, "no errors")

    retrieved = hm.get_session(session.session_id)
    check(retrieved is session, "session retrieved")
    check(len(hm.list_active_sessions()) == 1, "active sessions")

    # Handshake with invalid cert (validation failure)
    from infrastructure.service_mesh.security import CertificateRecord
    from datetime import datetime, timedelta

    bad_cert = CertificateRecord(
        cert_id="cert-bad",
        spiffe_id="spiffe://icyquant.local/x/y",
        issuer="unknown-ca",
        public_key="",  # empty public key -> signature check fails
        expires_at=datetime.utcnow() - timedelta(hours=1),  # expired
    )
    session2 = await hm.perform_handshake(
        client_identity="spiffe://icyquant.local/a/b",
        server_identity="spiffe://icyquant.local/c/d",
        client_cert=bad_cert,
    )
    check(session2.state == HandshakeState.FAILED, "handshake failed")
    check(len(session2.errors) > 0, "handshake errors recorded")

    stats = hm.get_stats()
    check(stats["handshake_count"] == 2, "handshake count stats")
    check(stats["success_count"] == 1, "success count stats")
    check(stats["failure_count"] == 1, "failure count stats")


# ============================================================
# 20. MTLSEngine
# ============================================================
async def test_mtls() -> None:
    report_section("20. MTLSEngine")
    from infrastructure.service_mesh.security import MTLSEngine

    engine = MTLSEngine()
    check(not engine.is_running, "not running")
    engine.start()
    check(engine.is_running, "started")

    # Establish successful mTLS session
    result = await engine.establish(
        client_identity="spiffe://icyquant.local/oms/client",
        server_identity="spiffe://icyquant.local/oms/server",
    )
    check(result["success"], "mtls established")
    check(result["session_id"], "session id present")
    check(result["client_identity"] == "spiffe://icyquant.local/oms/client", "client identity")
    check(result["server_identity"] == "spiffe://icyquant.local/oms/server", "server identity")

    session_id = result["session_id"]
    session = engine.get_session(session_id)
    check(session is not None, "session retrieved")
    check(session.is_active, "session active")
    check(session.client_identity == "spiffe://icyquant.local/oms/client", "session client")

    # Record activity
    check(engine.record_activity(session_id, sent=100, received=50), "activity recorded")
    check(session.bytes_sent == 100, "bytes sent")
    check(session.bytes_received == 50, "bytes received")

    check(len(engine.list_active_sessions()) == 1, "active sessions")
    check(engine.close_session(session_id), "session closed")
    check(not session.is_active, "session inactive")

    stats = engine.get_stats()
    check(stats["handshake_count"] == 1, "handshake count")
    check(stats["success_count"] == 1, "success count")
    engine.stop()


# ============================================================
# 21. AuthenticationManager
# ============================================================
async def test_authentication() -> None:
    report_section("21. AuthenticationManager")
    from infrastructure.service_mesh.security import (
        AuthenticationManager, AuthMethod,
    )

    auth = AuthenticationManager()

    # Certificate auth
    result = await auth.authenticate(
        AuthMethod.CERTIFICATE,
        {"cert_id": "cert-1", "spiffe_id": "spiffe://icyquant.local/oms/svc"},
    )
    check(result.success, "certificate auth success")
    check(result.principal is not None, "principal returned")
    check(result.principal.is_authenticated, "principal authenticated")
    check(
        result.principal.spiffe_id == "spiffe://icyquant.local/oms/svc",
        "principal spiffe id",
    )

    # Identity auth
    result2 = await auth.authenticate(
        AuthMethod.IDENTITY,
        {"spiffe_id": "spiffe://icyquant.local/risk/svc"},
    )
    check(result2.success, "identity auth success")

    # Workload auth
    result3 = await auth.authenticate(
        AuthMethod.WORKLOAD,
        {"service_name": "execution-engine", "namespace": "execution"},
    )
    check(result3.success, "workload auth success")
    check(
        result3.principal.spiffe_id == "spiffe://icyquant.local/execution/execution-engine",
        "workload spiffe id",
    )

    # Token auth with valid token
    token_rec = auth.token_provider.issue_token("spiffe://icyquant.local/oms/svc")
    result4 = await auth.authenticate(
        AuthMethod.TOKEN,
        {"token": token_rec.token},
    )
    check(result4.success, "token auth success")

    # Token auth with invalid token
    result5 = await auth.authenticate(
        AuthMethod.TOKEN,
        {"token": "invalid"},
    )
    check(not result5.success, "invalid token fails")

    # Missing credentials
    result6 = await auth.authenticate(
        AuthMethod.CERTIFICATE,
        {},
    )
    check(not result6.success, "missing credentials fails")

    # Unknown method
    result7 = await auth.authenticate("unknown", {})
    check(not result7.success, "unknown method fails")

    stats = auth.get_stats()
    check(stats["auth_count"] == 7, "auth count stats")


# ============================================================
# 22. AuthorizationManager
# ============================================================
async def test_authorization() -> None:
    report_section("22. AuthorizationManager")
    from infrastructure.service_mesh.security import (
        AuthorizationManager, PolicyEngine, SecurityPolicy,
        PolicyEffect, Principal,
    )

    policy_engine = PolicyEngine()
    # Default allow policy
    allow_policy = SecurityPolicy(
        policy_id="allow-all",
        effect=PolicyEffect.ALLOW,
        priority=10,
    )
    policy_engine.register_policy(allow_policy)
    # Deny policy for restricted namespace
    deny_policy = SecurityPolicy(
        policy_id="deny-restricted",
        effect=PolicyEffect.DENY,
        to_namespaces=["restricted"],
        priority=100,
    )
    policy_engine.register_policy(deny_policy)

    authz = AuthorizationManager(policy_engine=policy_engine)

    # Authenticated principal - allowed
    principal = Principal.from_spiffe_id("spiffe://icyquant.local/oms/svc")
    principal.mark_authenticated("certificate")
    result = await authz.authorize(principal, "orders", "access")
    check(result.allowed, "allowed by policy")
    check(result.policy_id == "allow-all", "allow policy id")

    # Denied by restricted namespace
    restricted_principal = Principal.from_spiffe_id("spiffe://icyquant.local/restricted/svc")
    restricted_principal.mark_authenticated("certificate")
    result2 = await authz.authorize(restricted_principal, "orders", "access")
    check(not result2.allowed, "denied by restricted namespace")
    check(result2.policy_id == "deny-restricted", "deny policy id")

    # Unauthenticated principal
    unauth = Principal.from_spiffe_id("spiffe://icyquant.local/oms/svc")
    result3 = await authz.authorize(unauth, "orders", "access")
    check(not result3.allowed, "unauthenticated denied")

    stats = authz.get_stats()
    check(stats["check_count"] == 3, "check count stats")
    check(stats["allow_count"] == 1, "allow count stats")
    check(stats["deny_count"] == 2, "deny count stats")


# ============================================================
# 23. PolicyEngine
# ============================================================
async def test_policy_engine() -> None:
    report_section("23. PolicyEngine")
    from infrastructure.service_mesh.security import (
        PolicyEngine, SecurityPolicy, PolicyEffect,
    )

    engine = PolicyEngine()
    check(engine.get_stats()["policy_count"] == 0, "no policies initially")

    # Default deny
    result = engine.evaluate(
        principal="spiffe://icyquant.local/oms/svc",
        resource="orders",
        action="access",
    )
    check(not result["allowed"], "default deny")
    check(result["reason"] == "default_deny", "default deny reason")

    # Register allow policy
    allow = SecurityPolicy(
        policy_id="allow-oms-to-orders",
        effect=PolicyEffect.ALLOW,
        from_services=["oms"],
        to_services=["orders"],
        methods=["access"],
        priority=50,
    )
    engine.register_policy(allow)
    check(engine.get_policy("allow-oms-to-orders") is allow, "policy retrieved")
    check(len(engine.list_policies()) == 1, "list policies")

    result2 = engine.evaluate(
        principal="spiffe://icyquant.local/oms/svc",
        resource="orders",
        action="access",
    )
    check(result2["allowed"], "allowed by policy")
    check(result2["policy_id"] == "allow-oms-to-to-orders".replace("-to-to-", "-to-"), "allow policy id match")

    # Deny takes precedence
    deny = SecurityPolicy(
        policy_id="deny-oms",
        effect=PolicyEffect.DENY,
        from_services=["oms"],
        priority=100,  # higher priority
    )
    engine.register_policy(deny)
    result3 = engine.evaluate(
        principal="spiffe://icyquant.local/oms/svc",
        resource="orders",
        action="access",
    )
    check(not result3["allowed"], "denied by deny policy")
    check(result3["policy_id"] == "deny-oms", "deny policy id")

    # Unregister
    check(engine.unregister_policy("deny-oms"), "policy unregistered")
    result4 = engine.evaluate(
        principal="spiffe://icyquant.local/oms/svc",
        resource="orders",
        action="access",
    )
    check(result4["allowed"], "allowed after deny removed")

    stats = engine.get_stats()
    check(stats["policy_count"] == 1, "policy count stats")
    check(stats["evaluation_count"] == 4, "evaluation count stats")


# ============================================================
# 24. PolicyRepository
# ============================================================
async def test_policy_repository() -> None:
    report_section("24. PolicyRepository")
    from infrastructure.service_mesh.security import (
        PolicyRepository, SecurityPolicy, PolicyEffect,
    )

    repo = PolicyRepository()
    p1 = SecurityPolicy(policy_id="pol-1", effect=PolicyEffect.ALLOW)
    p2 = SecurityPolicy(policy_id="pol-2", effect=PolicyEffect.DENY)
    repo.add(p1)
    repo.add(p2)
    check(repo.get("pol-1") is p1, "policy retrieved")
    check(len(repo.list_all()) == 2, "list all")

    v1 = repo.commit_version()
    check(v1 == 1, "first version")
    check(len(repo.list_versions()) == 1, "version count")

    # Modify and commit
    repo.remove("pol-1")
    p3 = SecurityPolicy(policy_id="pol-3", effect=PolicyEffect.ALLOW)
    repo.add(p3)
    v2 = repo.commit_version()
    check(v2 == 2, "second version")
    check(len(repo.list_all()) == 2, "after modification")

    # Rollback to v1
    check(repo.rollback(1), "rollback to v1")
    check(repo.get("pol-1") is not None, "pol-1 restored")
    check(repo.get("pol-3") is None, "pol-3 removed")
    check(len(repo.list_all()) == 2, "after rollback")

    stats = repo.get_stats()
    check(stats["version_count"] == 2, "version count stats")
    check(stats["current_version"] == 1, "current version stats")


# ============================================================
# 25. SecurityManager (Orchestration)
# ============================================================
async def test_security_manager() -> None:
    report_section("25. SecurityManager")
    from infrastructure.service_mesh.security import (
        SecurityManager, SecurityPolicy, PolicyEffect, Principal,
    )

    mgr = SecurityManager(trust_domain="icyquant.local")
    check(not mgr.is_running, "not running initially")

    # Initialize
    result = await mgr.initialize()
    check(result["success"], "initialized")
    check(result["trust_domain"] == "icyquant.local", "trust domain")
    check(mgr.is_running, "running after init")

    # Create workload identity
    wi = await mgr.create_workload_identity(
        service_name="order-service",
        namespace="execution",
        instance_id="pod-1",
        ttl_seconds=3600,
    )
    check(wi["spiffe_id"] == "spiffe://icyquant.local/execution/order-service/pod-1", "workload spiffe")
    check(wi["identity_id"], "workload identity id")

    # Issue certificate
    cert = await mgr.issue_certificate(
        spiffe_id=wi["spiffe_id"],
        cert_type="workload",
        ttl_hours=24,
    )
    check(cert["cert_id"], "certificate id")
    check(cert["spiffe_id"] == wi["spiffe_id"], "cert spiffe")

    # Establish mTLS
    mtls = await mgr.establish_mtls(
        client_identity="spiffe://icyquant.local/execution/order-service/pod-1",
        server_identity="spiffe://icyquant.local/execution/matching-engine",
    )
    check(mtls["success"], "mtls established")
    check(mtls["session_id"], "mtls session id")

    # Register policy
    policy = SecurityPolicy(
        policy_id="test-allow",
        effect=PolicyEffect.ALLOW,
        from_services=["order-service"],
        to_services=["matching-engine"],
        priority=50,
    )
    mgr.register_policy(policy)
    check(mgr.get_policy("test-allow") is policy, "policy registered")
    check(len(mgr.list_policies()) == 1, "list policies")

    # Authenticate
    auth_result = await mgr.authenticate(
        method="certificate",
        credentials={
            "cert_id": cert["cert_id"],
            "spiffe_id": wi["spiffe_id"],
        },
    )
    check(auth_result["success"], "authenticated")
    check(auth_result["principal"] is not None, "principal returned")

    # Authorize
    principal = Principal.from_spiffe_id(wi["spiffe_id"])
    principal.mark_authenticated("certificate")
    authz_result = await mgr.authorize(
        principal=principal,
        resource="matching-engine",
        action="access",
    )
    check(authz_result["allowed"], "authorized")

    # Health check
    health = await mgr.health_check()
    check("components" in health, "health components")
    check("cert_manager" in health["components"], "cert_manager in security health")

    # Stats
    stats = mgr.get_stats()
    check(stats["started"], "stats started")
    check(stats["trust_domain"] == "icyquant.local", "stats trust domain")
    check("metrics" in stats, "stats metrics")
    check("certificates" in stats, "stats certificates")
    check("mtls" in stats, "stats mtls")
    check("policies" in stats, "stats policies")
    check("audit" in stats, "stats audit")

    # Shutdown
    shutdown_result = await mgr.shutdown()
    check(shutdown_result["success"], "shutdown success")
    check(not mgr.is_running, "not running after shutdown")


# ============================================================
# 26. SecurityScheduler
# ============================================================
async def test_security_scheduler() -> None:
    report_section("26. SecurityScheduler")
    from infrastructure.service_mesh.security import (
        SecurityScheduler, SecurityScheduledTask,
    )

    scheduler = SecurityScheduler()
    check(not scheduler.is_running, "not running")

    call_count = 0

    def sync_task():
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    async def async_task():
        return {"ok": True}

    scheduler.register_task("sync-task", sync_task, interval_s=0.1)
    scheduler.register_task("async-task", async_task, interval_s=0.1)
    check(len(scheduler.get_stats()["tasks"]) == 2, "tasks registered")

    # Disable a task
    check(scheduler.disable_task("sync-task"), "task disabled")
    status = scheduler.get_task_status("sync-task")
    check(status is not None, "task status retrieved")
    check(not status["enabled"], "task disabled status")

    check(scheduler.enable_task("sync-task"), "task enabled")
    check(scheduler.get_task_status("sync-task")["enabled"], "task enabled status")

    # Start scheduler
    await scheduler.start()
    check(scheduler.is_running, "scheduler running")
    # Allow tasks to run (must use async sleep to yield control)
    await asyncio.sleep(0.5)
    await scheduler.stop()
    check(not scheduler.is_running, "scheduler stopped")

    status2 = scheduler.get_task_status("sync-task")
    check(status2["run_count"] >= 1, "task ran at least once")

    # Unregister
    check(scheduler.unregister_task("sync-task"), "task unregistered")
    check(scheduler.get_task_status("sync-task") is None, "task gone")


# ============================================================
# 27. ServiceMesh Security Integration
# ============================================================
async def test_mesh_security_integration() -> None:
    report_section("27. ServiceMesh Security Integration")
    from infrastructure.service_mesh import ServiceMesh
    from infrastructure.service_mesh.security import (
        SecurityManager, SecurityScheduler,
    )

    mesh = ServiceMesh(mesh_id="security-test-mesh")
    check(isinstance(mesh.security_manager, SecurityManager), "security manager property")
    check(isinstance(mesh.security_scheduler, SecurityScheduler), "security scheduler property")

    # Start mesh
    result = await mesh.startup(timeout_s=30.0)
    check(result.get("bootstrapped"), "mesh bootstrapped")
    check(mesh.is_running, "mesh running")
    check(mesh.security_manager.is_running, "security manager running")

    # Stats include security
    stats = mesh.get_stats()
    check("security" in stats, "security stats present")
    check(stats["security"]["started"], "security stats started")

    # Health check includes security_manager
    health = await mesh.health_check()
    check(
        "security_manager" in health.get("components", {}),
        "security_manager in mesh health",
    )

    # Shutdown
    shutdown = await mesh.shutdown()
    check(shutdown["success"], "mesh shutdown")
    check(not mesh.security_manager.is_running, "security stopped")


# ============================================================
# Main
# ============================================================
async def main() -> None:
    global FAILED
    print("=" * 60)
    print("ICYQuant Service Mesh Security - Validation Suite")
    print("=" * 60)

    tests = [
        test_exceptions,
        test_metrics,
        test_telemetry,
        test_audit,
        test_diagnostics,
        test_identity,
        test_workload_identity,
        test_trust_domain,
        test_spiffe,
        test_certificate_authority,
        test_certificate_store,
        test_certificate_manager,
        test_certificate_validator,
        test_revocation,
        test_certificate_rotator,
        test_key_manager,
        test_secret_provider,
        test_token_provider,
        test_handshake,
        test_mtls,
        test_authentication,
        test_authorization,
        test_policy_engine,
        test_policy_repository,
        test_security_manager,
        test_security_scheduler,
        test_mesh_security_integration,
    ]

    for test in tests:
        try:
            await test()
        except Exception:
            FAILED += 1
            FAILURES.append(
                f"  - EXCEPTION in {test.__name__}: {traceback.format_exc()}"
            )

    print("\n" + "=" * 60)
    print(f"Results: {PASSED} passed, {FAILED} failed")
    if FAILURES:
        print("\nFailures:")
        for failure in FAILURES:
            print(failure)
    print("=" * 60)

    return FAILED


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
