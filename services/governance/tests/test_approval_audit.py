"""
Tests for audit — Authority audit and Delegation audit records.

Tests the new Part 1.3 audit classes:
  - AuthorityAuditRecord, AuthorityAuditAction, AuthorityAuditStore
  - DelegationAuditRecord, DelegationAuditAction, DelegationAuditStore

Covers spec test requirements:
  - Audit records for authority changes and delegations
  - Query by actor, time range, and action type
"""

import sys, os, unittest, types, importlib.util, time

# --- Setup virtual package hierarchy ---
_gov_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_services_dir = os.path.dirname(_gov_dir)
_project_root = os.path.dirname(_services_dir)
sys.path.insert(0, _project_root)

_svc = types.ModuleType("services"); _svc.__path__ = [_services_dir]; _svc.__package__ = "services"
sys.modules["services"] = _svc
_gov = types.ModuleType("services.governance"); _gov.__path__ = [_gov_dir]; _gov.__package__ = "services.governance"
sys.modules["services.governance"] = _gov
_s = importlib.util.spec_from_file_location("services.governance.__init__", os.path.join(_gov_dir, "__init__.py"), submodule_search_locations=[_gov_dir])
_m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)

from services.governance.approval_audit import ApprovalAudit
from services.governance.authority_audit import (
    AuthorityAuditRecord, AuthorityAuditAction, AuthorityAuditStore,
)
from services.governance.delegation_audit import (
    DelegationAuditRecord, DelegationAuditAction, DelegationAuditStore,
)


class TestAuthorityAudit(unittest.TestCase):
    """Authority audit records."""

    def setUp(self):
        self.store = AuthorityAuditStore()

    def test_grant_record(self):
        record = AuthorityAuditRecord.create_grant_record(
            actor="PM-User", grant_id="G-001", authority_level="APPROVAL",
            max_amount=20_000_000, scope="PORTFOLIO",
            performed_by="ADMIN", reason="New PM role",
        )
        self.store.record(record)
        self.assertEqual(self.store.count(), 1)

    def test_revoke_record(self):
        record = AuthorityAuditRecord.create_revoke_record(
            actor="PM-User", grant_id="G-001", authority_level="APPROVAL",
            max_amount=20_000_000, performed_by="ADMIN", reason="Resigned",
        )
        self.store.record(record)
        self.assertEqual(self.store.count(), 1)

    def test_delegation_record(self):
        record = AuthorityAuditRecord.create_delegation_record(
            delegator="PM", delegate="DEP", delegation_id="DEL-001",
            max_amount=10_000_000, performed_by="PM",
            reason="Temporary coverage",
        )
        self.store.record(record)
        self.assertEqual(self.store.count(), 1)

    def test_query_by_actor(self):
        r1 = AuthorityAuditRecord.create_grant_record("User-A", "G1", "APR", 10_000_000)
        r2 = AuthorityAuditRecord.create_grant_record("User-B", "G2", "APR", 20_000_000)
        r3 = AuthorityAuditRecord.create_revoke_record("User-A", "G1", "APR", 10_000_000)
        self.store.record(r1)
        self.store.record(r2)
        self.store.record(r3)
        results = self.store.get_by_actor("User-A")
        self.assertEqual(len(results), 2)

    def test_query_by_action(self):
        r1 = AuthorityAuditRecord.create_grant_record("A", "G1", "APR", 10_000_000)
        r2 = AuthorityAuditRecord.create_revoke_record("A", "G1", "APR", 10_000_000)
        self.store.record(r1)
        self.store.record(r2)
        grants = self.store.get_by_action(AuthorityAuditAction.GRANT)
        revokes = self.store.get_by_action(AuthorityAuditAction.REVOKE)
        self.assertEqual(len(grants), 1)
        self.assertEqual(len(revokes), 1)

    def test_query_by_grant(self):
        r1 = AuthorityAuditRecord.create_grant_record("A", "G-ABC", "APR", 10_000_000)
        r2 = AuthorityAuditRecord.create_revoke_record("A", "G-ABC", "APR", 10_000_000)
        r3 = AuthorityAuditRecord.create_grant_record("B", "G-XYZ", "APR", 20_000_000)
        self.store.record(r1)
        self.store.record(r2)
        self.store.record(r3)
        results = self.store.get_by_grant("G-ABC")
        self.assertEqual(len(results), 2)

    def test_query_by_time_range(self):
        now = time.time()
        r1 = AuthorityAuditRecord.create_grant_record("A", "G1", "APR", 10_000_000)
        r1.timestamp = now - 100
        r2 = AuthorityAuditRecord.create_revoke_record("A", "G1", "APR", 10_000_000)
        r2.timestamp = now + 100
        self.store.record(r1)
        self.store.record(r2)
        early = self.store.get_by_time_range(now - 200, now - 50)
        self.assertEqual(len(early), 1)
        self.assertEqual(early[0].action, AuthorityAuditAction.GRANT)


class TestDelegationAudit(unittest.TestCase):
    """Delegation audit records."""

    def setUp(self):
        self.store = DelegationAuditStore()

    def test_create_record(self):
        record = DelegationAuditRecord.created(
            delegation_id="DEL-001", delegator="PM", delegate="DEPUTY",
            max_amount=10_000_000, scope="PORTFOLIO A",
            reason="Temporary coverage",
        )
        self.store.record(record)
        self.assertEqual(self.store.count(), 1)

    def test_revoked_record(self):
        record = DelegationAuditRecord.revoked(
            delegation_id="DEL-001", delegator="PM", delegate="DEPUTY",
            reason="No longer needed", performed_by="PM",
        )
        self.store.record(record)
        self.assertEqual(self.store.count(), 1)

    def test_expired_record(self):
        record = DelegationAuditRecord.expired("DEL-001", "PM", "DEPUTY")
        self.store.record(record)
        self.assertEqual(self.store.count(), 1)

    def test_query_by_delegator(self):
        r1 = DelegationAuditRecord.created("D1", "PM-A", "DEP1", 10_000_000)
        r2 = DelegationAuditRecord.created("D2", "PM-B", "DEP2", 20_000_000)
        r3 = DelegationAuditRecord.revoked("D1", "PM-A", "DEP1", "Done")
        self.store.record(r1)
        self.store.record(r2)
        self.store.record(r3)
        pm_a = self.store.get_by_delegator("PM-A")
        self.assertEqual(len(pm_a), 2)

    def test_query_by_action(self):
        r1 = DelegationAuditRecord.created("D1", "PM", "DEP", 10_000_000)
        r2 = DelegationAuditRecord.revoked("D1", "PM", "DEP", "Done")
        self.store.record(r1)
        self.store.record(r2)
        created = self.store.get_by_action(DelegationAuditAction.CREATED)
        revoked = self.store.get_by_action(DelegationAuditAction.REVOKED)
        self.assertEqual(len(created), 1)
        self.assertEqual(len(revoked), 1)

    def test_query_by_delegate(self):
        r1 = DelegationAuditRecord.created("D1", "PM-A", "DEPUTY-X", 10_000_000)
        r2 = DelegationAuditRecord.created("D2", "PM-B", "DEPUTY-Y", 20_000_000)
        self.store.record(r1)
        self.store.record(r2)
        results = self.store.get_by_delegate("DEPUTY-X")
        self.assertEqual(len(results), 1)


class TestApprovalAuditIntegration(unittest.TestCase):
    """Existing ApprovalAudit record keeping."""

    def test_record_approval(self):
        audit = ApprovalAudit()
        audit.record(
            approval_id="APR-001",
            approval_request_id="REQ-001",
            decision_request_id="DEC-001",
            decision="APPROVED",
            level="INTERNAL",
            reason="Meets policy",
            steps_completed=["STEP-1"],
            context={"amount": 10_000_000},
        )
        self.assertGreaterEqual(audit.count(), 1)

    def test_count_records(self):
        audit = ApprovalAudit()
        audit.record("A1", "R1", "D1", "APPROVED", "HIGH", "ok", ["S1"], {"x": 1})
        audit.record("A2", "R2", "D2", "REJECTED", "LOW", "bad", ["S1"], {"x": 2})
        self.assertEqual(audit.count(), 2)


if __name__ == "__main__":
    unittest.main()
