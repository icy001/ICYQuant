"""
Tests for approval_manager, approval_controller, and approval infrastructure.

Covers spec test requirements:
  - Approval: Create, Submit, Approve, Reject, Expire, Cancel, Invalidate
"""

import sys, os, unittest, types, importlib.util

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

from services.governance.approval_manager import ApprovalManager
from services.governance.approval_controller import ApprovalController
from services.governance.approval_request import ApprovalRequest, ApprovalRequestStatus
from services.governance.approval_repository import ApprovalRepository, InMemoryApprovalBackend
from services.governance.approval_threshold import ApprovalThreshold, ThresholdTier


def _make_manager():
    repo = ApprovalRepository(backend=InMemoryApprovalBackend())
    return ApprovalManager(repository=repo)


class TestApprovalCreate(unittest.TestCase):
    """Create approval requests."""

    def setUp(self):
        self.mgr = _make_manager()

    def test_create_request(self):
        req = self.mgr.create_request(
            decision_request_id="DEC-001", decision_type="CAPITAL_ALLOCATION",
            amount=25_000_000, risk=1_000_000, reason="Test allocation",
        )
        self.assertIsNotNone(req)
        self.assertEqual(req.decision_request_id, "DEC-001")
        self.assertEqual(req.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(req.amount, 25_000_000)

    def test_create_defaults(self):
        req = self.mgr.create_request(
            decision_request_id="DEC-002", decision_type="AUDIT",
        )
        self.assertEqual(req.amount, 0.0)
        self.assertEqual(req.risk, 0.0)
        self.assertEqual(req.level, "INTERNAL")

    def test_create_unique_ids(self):
        req1 = self.mgr.create_request(decision_request_id="D1", decision_type="T")
        req2 = self.mgr.create_request(decision_request_id="D2", decision_type="T")
        self.assertNotEqual(req1.request_id, req2.request_id)


class TestApprovalApproveReject(unittest.TestCase):
    """Approve and reject requests."""

    def setUp(self):
        self.mgr = _make_manager()

    def test_approve(self):
        req = self.mgr.create_request(
            decision_request_id="DEC-001", decision_type="CAP", amount=10_000_000,
        )
        resp = self.mgr.approve(req, "approver1", "Looks good")
        self.assertTrue(resp.approved)
        self.assertEqual(resp.status.name, "APPROVED")
        self.assertEqual(resp.approved_amount, 10_000_000)

    def test_reject(self):
        req = self.mgr.create_request(decision_request_id="DEC-002", decision_type="CAP")
        resp = self.mgr.reject(req, "approver1", "Too risky")
        self.assertFalse(resp.approved)
        self.assertEqual(resp.reject_reason, "Too risky")

    def test_cannot_approve_twice(self):
        req = self.mgr.create_request(decision_request_id="DEC-003", decision_type="CAP")
        self.mgr.approve(req, "a", "ok")
        with self.assertRaises(ValueError):
            self.mgr.approve(req, "b", "again")

    def test_cannot_reject_approved(self):
        req = self.mgr.create_request(decision_request_id="DEC-004", decision_type="CAP")
        self.mgr.approve(req, "a", "ok")
        with self.assertRaises(ValueError):
            self.mgr.reject(req, "b", "no")


class TestApprovalCancelExpire(unittest.TestCase):
    """Cancel and expire requests."""

    def setUp(self):
        self.mgr = _make_manager()

    def test_cancel_pending(self):
        req = self.mgr.create_request(decision_request_id="DEC-001", decision_type="CAP")
        req = self.mgr.cancel(req, "tester", "Changed mind")
        self.assertEqual(req.status, ApprovalRequestStatus.CANCELLED)

    def test_expire_pending(self):
        req = self.mgr.create_request(decision_request_id="DEC-001", decision_type="CAP")
        req = self.mgr.expire(req)
        self.assertEqual(req.status, ApprovalRequestStatus.EXPIRED)

    def test_cannot_expire_approved(self):
        req = self.mgr.create_request(decision_request_id="DEC-001", decision_type="CAP")
        req = self.mgr.approve(req, "a", "ok")
        req2 = self.mgr.get_request(req.request_id)
        with self.assertRaises(ValueError):
            self.mgr.expire(req2)

    def test_expire_overdue(self):
        self.mgr.create_request(decision_request_id="DEC-001", decision_type="CAP", ttl_seconds=-1)
        count = self.mgr.expire_all_overdue()
        self.assertGreaterEqual(count, 1)


class TestApprovalController(unittest.TestCase):
    """ApprovalController integration tests."""

    def setUp(self):
        self.controller = ApprovalController()

    def test_requires_approval(self):
        threshold = ApprovalThreshold(
            threshold_id="TH-CAP", name="Capital Threshold", decision_type="CAPITAL_ALLOCATION",
            tiers=[
                ThresholdTier(name="Auto", max_amount=5_000_000, authority_levels=[]),
                ThresholdTier(name="Review", max_amount=20_000_000, authority_levels=["RISK_MANAGER"]),
            ],
        )
        self.controller.register_threshold(threshold)
        self.assertFalse(self.controller.requires_approval("CAPITAL_ALLOCATION", 3_000_000))
        self.assertTrue(self.controller.requires_approval("CAPITAL_ALLOCATION", 15_000_000))

    def test_initiate_and_approve(self):
        threshold = ApprovalThreshold(
            threshold_id="TH-CAP", name="CT", decision_type="CAP",
            tiers=[ThresholdTier(name="R", max_amount=50_000_000, authority_levels=["RISK_MANAGER"])],
        )
        self.controller.register_threshold(threshold)
        req = self.controller.initiate_approval(
            decision_request_id="DEC-001", decision_type="CAP", amount=10_000_000,
        )
        self.assertIsNotNone(req)
        resp = self.controller.approve(req.request_id, "RM", "Approved")
        self.assertTrue(resp.approved)

    def test_reject_via_controller(self):
        req = self.controller.initiate_approval(
            decision_request_id="DEC-002", decision_type="CAP", amount=5_000_000,
        )
        resp = self.controller.reject(req.request_id, "RM", "Bad risk")
        self.assertFalse(resp.approved)


class TestThresholdResolution(unittest.TestCase):
    """ApprovalThreshold resolution."""

    def test_resolve_autonomous(self):
        t = ApprovalThreshold("TH", "T", "CAP", tiers=[ThresholdTier("Auto", 5_000_000, [])])
        r = t.resolve(3_000_000)
        self.assertFalse(r.approval_required)

    def test_resolve_requires_approval(self):
        t = ApprovalThreshold("TH", "T", "CAP", tiers=[
            ThresholdTier("Auto", 5_000_000, []),
            ThresholdTier("Review", 20_000_000, ["RISK_MANAGER"]),
        ])
        r = t.resolve(10_000_000)
        self.assertTrue(r.approval_required)
        self.assertEqual(r.matched_tier, "Review")


class TestResponseConsumption(unittest.TestCase):
    """Approval response replay protection."""

    def test_single_consume(self):
        from services.governance.approval_response import ApprovalResponse
        from services.governance.approval_status import ApprovalStatus
        resp = ApprovalResponse(approval_id="A1", request_id="R1", decision_id="D1",
                                status=ApprovalStatus.APPROVED, approved=True, approved_amount=10_000_000)
        self.assertTrue(resp.is_valid())
        self.assertTrue(resp.consume())
        self.assertTrue(resp.consumed)
        self.assertFalse(resp.is_valid())
        self.assertFalse(resp.consume())


if __name__ == "__main__":
    unittest.main()
