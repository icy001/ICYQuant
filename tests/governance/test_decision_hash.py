"""Decision hashing (Commit 28 Part 1.5).

- Entry hash: deterministic SHA-256 over the canonical entry payload.
- Context hash: canonical serialization (key order must not matter).
- Request fingerprint: principal + resource + action + parameters + context.
"""

from datetime import datetime, timezone

from services.governance.decision_ledger import (
    calculate_hash,
    request_fingerprint,
)
from services.governance.evidence import (
    canonicalize_context,
    context_hash,
    evidence_hash,
)
from services.governance.evidence import GovernanceEvidence

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


class TestCalculateHash:

    def test_hash_is_deterministic(self):
        h1 = calculate_hash(1, "DEC-001", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, None)
        h2 = calculate_hash(1, "DEC-001", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, None)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_changes_with_any_field(self):
        base = calculate_hash(1, "DEC-001", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, None)
        assert calculate_hash(2, "DEC-001", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, None) != base
        assert calculate_hash(1, "DEC-002", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, None) != base
        assert calculate_hash(1, "DEC-001", "REQ-002", "ALLOW", "GOV_ALLOWED", NOW, None) != base
        assert calculate_hash(1, "DEC-001", "REQ-001", "DENY", "GOV_ALLOWED", NOW, None) != base
        assert calculate_hash(1, "DEC-001", "REQ-001", "ALLOW", "GOV_DENIED", NOW, None) != base
        assert calculate_hash(1, "DEC-001", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, "prev") != base

    def test_timestamp_changes_hash(self):
        h1 = calculate_hash(1, "DEC-001", "REQ-001", "ALLOW", "GOV_ALLOWED", NOW, None)
        h2 = calculate_hash(
            1,
            "DEC-001",
            "REQ-001",
            "ALLOW",
            "GOV_ALLOWED",
            NOW.replace(minute=1),
            None,
        )
        assert h1 != h2


class TestCanonicalContext:

    def test_key_order_does_not_matter(self):
        a = canonicalize_context({"a": 1, "b": 2})
        b = canonicalize_context({"b": 2, "a": 1})
        assert a == b

    def test_context_hash_is_order_independent(self):
        assert context_hash({"a": 1, "b": 2}) == context_hash({"b": 2, "a": 1})

    def test_context_hash_changes_with_content(self):
        base = context_hash({"a": 1, "b": 2})
        assert context_hash({"a": 1, "b": 3}) != base
        assert context_hash({"a": 1}) != base

    def test_nested_context_is_stable(self):
        ctx = {"market": {"status": "OPEN"}, "risk": {"limit": 0.5}}
        assert context_hash(ctx) == context_hash(ctx)
        assert context_hash(ctx) != context_hash({"market": {"status": "CLOSED"}, "risk": {"limit": 0.5}})


class TestRequestFingerprint:

    def test_same_request_same_fingerprint(self):
        assert request_fingerprint("ops-001", "trading", "kill") == request_fingerprint(
            "ops-001", "trading", "kill"
        )

    def test_parameters_change_fingerprint(self):
        base = request_fingerprint("ops-001", "trading", "kill", parameters={"size": 100})
        assert request_fingerprint("ops-001", "trading", "kill", parameters={"size": 200}) != base

    def test_context_hash_change_fingerprint(self):
        base = request_fingerprint("ops-001", "trading", "kill", context_hash="ctx-1")
        assert request_fingerprint("ops-001", "trading", "kill", context_hash="ctx-2") != base

    def test_fingerprint_is_a_sha256_hexdigest(self):
        fp = request_fingerprint("ops-001", "trading", "kill")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestEvidenceHash:

    def test_evidence_hash_is_deterministic(self):
        evidence = GovernanceEvidence(
            decision_id="DEC-001",
            policy_id="POLICY-RESUME",
            policy_version="v3",
            principal_id="ops-001",
            authority_snapshot=("CONTROL_OPERATOR",),
            approval_id="APR-001",
            approval_state="APPROVED",
            quorum_met=True,
            context_hash="ctx-1",
            created_at=NOW,
        )
        assert evidence_hash(evidence) == evidence_hash(evidence)

    def test_evidence_hash_changes_with_fields(self):
        evidence = GovernanceEvidence(
            decision_id="DEC-001",
            policy_id="POLICY-RESUME",
            policy_version="v3",
            principal_id="ops-001",
            authority_snapshot=("CONTROL_OPERATOR",),
            approval_id="APR-001",
            approval_state="APPROVED",
            quorum_met=True,
            context_hash="ctx-1",
            created_at=NOW,
        )
        modified = GovernanceEvidence(
            decision_id="DEC-001",
            policy_id="POLICY-RESUME",
            policy_version="v4",
            principal_id="ops-001",
            authority_snapshot=("CONTROL_OPERATOR",),
            approval_id="APR-001",
            approval_state="APPROVED",
            quorum_met=True,
            context_hash="ctx-1",
            created_at=NOW,
        )
        assert evidence_hash(modified) != evidence_hash(evidence)
