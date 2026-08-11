"""
Tests for Decision Audit — recording and querying audit records.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.governance.decision_audit import DecisionAudit, AuditRecord
from services.governance.governance_audit import GovernanceAudit, GovernanceAuditReport
from services.governance.policy_audit import PolicyAudit
from services.governance.approval_audit import ApprovalAudit


class TestDecisionAudit:

    @pytest.fixture
    def auditor(self):
        return DecisionAudit(max_records=1000)

    def _make_record(self, decision_id, actor="SYSTEM", verdict="ALLOW", **kwargs):
        return AuditRecord(
            decision_id=decision_id,
            request_id=f"REQ-{decision_id}",
            actor=actor,
            decision_type="CAPITAL_ALLOCATION",
            verdict=verdict,
            reason="Test reason",
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Basic record/query
    # ------------------------------------------------------------------

    def test_record_and_get(self, auditor):
        record = self._make_record("GOV-001")
        auditor.record(record)

        retrieved = auditor.get("GOV-001")
        assert retrieved is not None
        assert retrieved.verdict == "ALLOW"

    def test_get_nonexistent(self, auditor):
        assert auditor.get("NONEXISTENT") is None

    def test_record_multiple(self, auditor):
        for i in range(10):
            verdict = "ALLOW" if i % 2 == 0 else "BLOCKED"
            auditor.record(self._make_record(f"GOV-{i:03d}", verdict=verdict))

        assert auditor.count() == 10

    # ------------------------------------------------------------------
    # Query filters
    # ------------------------------------------------------------------

    def test_query_by_actor(self, auditor):
        auditor.record(self._make_record("GOV-001", actor="SYSTEM"))
        auditor.record(self._make_record("GOV-002", actor="RISK_ENGINE"))
        auditor.record(self._make_record("GOV-003", actor="SYSTEM"))

        results = auditor.query(actor="SYSTEM")
        assert len(results) == 2

        results = auditor.query(actor="RISK_ENGINE")
        assert len(results) == 1

    def test_query_by_verdict(self, auditor):
        auditor.record(self._make_record("GOV-001", verdict="ALLOW"))
        auditor.record(self._make_record("GOV-002", verdict="BLOCKED"))
        auditor.record(self._make_record("GOV-003", verdict="ALLOW"))

        blocked = auditor.query(verdict="BLOCKED")
        assert len(blocked) == 1

        allowed = auditor.query(verdict="ALLOW")
        assert len(allowed) == 2

    def test_query_by_decision_type(self, auditor):
        auditor.record(self._make_record("GOV-001"))
        auditor.record(AuditRecord(
            decision_id="GOV-002", request_id="R2", actor="SYSTEM",
            decision_type="EMERGENCY_ACTION", verdict="ALLOW",
        ))

        results = auditor.query(decision_type="EMERGENCY_ACTION")
        assert len(results) == 1

    # ------------------------------------------------------------------
    # Convenience queries
    # ------------------------------------------------------------------

    def test_get_recent(self, auditor):
        for i in range(5):
            auditor.record(self._make_record(f"GOV-{i:03d}"))

        recent = auditor.get_recent(3)
        assert len(recent) == 3

    def test_get_blocked_decisions(self, auditor):
        auditor.record(self._make_record("GOV-001", verdict="ALLOW"))
        auditor.record(self._make_record("GOV-002", verdict="BLOCKED"))
        auditor.record(self._make_record("GOV-003", verdict="REJECTED"))

        blocked = auditor.get_blocked_decisions()
        assert len(blocked) == 2

    def test_get_overrides(self, auditor):
        auditor.record(self._make_record("GOV-001"))
        auditor.record(self._make_record("GOV-002", override=True,
                                          override_reason="Emergency"))

        overrides = auditor.get_overrides()
        assert len(overrides) == 1

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def test_stats(self, auditor):
        auditor.record(self._make_record("GOV-001", verdict="ALLOW"))
        auditor.record(self._make_record("GOV-002", verdict="BLOCKED"))
        auditor.record(self._make_record("GOV-003", verdict="ALLOW"))

        stats = auditor.stats()
        assert stats["total"] == 3
        assert stats["verdicts"]["ALLOW"] == 2
        assert stats["verdicts"]["BLOCKED"] == 1

    def test_empty_stats(self, auditor):
        stats = auditor.stats()
        assert stats["total"] == 0

    # ------------------------------------------------------------------
    # Get by request
    # ------------------------------------------------------------------

    def test_get_by_request(self, auditor):
        auditor.record(AuditRecord(
            decision_id="GOV-001", request_id="REQ-SPECIAL",
            actor="SYSTEM", decision_type="CAPITAL_ALLOCATION",
            verdict="ALLOW",
        ))
        result = auditor.get_by_request("REQ-SPECIAL")
        assert result is not None
        assert result["decision_id"] == "GOV-001"


class TestGovernanceAudit:

    @pytest.fixture
    def gov_audit(self):
        return GovernanceAudit()

    def test_generate_report_empty(self, gov_audit):
        report = gov_audit.generate_report()
        assert report.total_decisions == 0

    def test_generate_report_with_data(self, gov_audit):
        for i in range(5):
            gov_audit.decision.record(AuditRecord(
                decision_id=f"GOV-{i}",
                request_id=f"R{i}",
                actor="SYSTEM",
                decision_type="CAPITAL_ALLOCATION",
                verdict="ALLOW" if i % 2 == 0 else "BLOCKED",
            ))

        report = gov_audit.generate_report()
        assert report.total_decisions == 5


class TestPolicyAudit:

    @pytest.fixture
    def audit(self):
        return PolicyAudit()

    def test_record_and_query(self, audit):
        audit.record("DEC-001", "REQ-001", "POL-001", "Test Policy",
                      passed=False, violations=[{"rule": "r1"}], warnings=[])

        results = audit.get_by_decision("DEC-001")
        assert len(results) == 1
        assert results[0]["passed"] is False

    def test_violation_count(self, audit):
        audit.record("D1", "R1", "P1", "P1", passed=True, violations=[], warnings=[])
        audit.record("D2", "R2", "P1", "P1", passed=False, violations=[{"rule": "r1"}], warnings=[])

        assert audit.violation_count() == 1


class TestApprovalAudit:

    @pytest.fixture
    def audit(self):
        return ApprovalAudit()

    def test_record_and_query(self, audit):
        audit.record(
            approval_id="APR-001",
            approval_request_id="AR-001",
            decision_request_id="DR-001",
            decision="APPROVED",
            level="INTERNAL",
            reason="Test",
            steps_completed=["step1", "step2"],
            context={},
        )

        result = audit.get_by_decision("DR-001")
        assert result is not None
        assert result["decision"] == "APPROVED"

    def test_approval_rate(self, audit):
        audit.record("A1", "AR1", "DR1", "APPROVED", "INTERNAL", "", [], {})
        audit.record("A2", "AR2", "DR2", "REJECTED", "INTERNAL", "", [], {})

        assert audit.approval_rate() == 0.5

    def test_stats(self, audit):
        audit.record("A1", "AR1", "DR1", "APPROVED", "INTERNAL", "", [], {})
        audit.record("A2", "AR2", "DR2", "REJECTED", "RISK_REVIEW", "", [], {})

        stats = audit.stats()
        assert stats["total"] == 2
        assert stats["decisions"]["APPROVED"] == 1
