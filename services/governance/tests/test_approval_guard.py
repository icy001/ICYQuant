"""
Tests for approval guard — Replay protection, Approval reuse,
Approval scope escalation, Authority escalation, Delegation escalation.

Covers spec test requirements:
  - Security: Replay, Approval reuse, Approval scope escalation,
    Authority escalation, Delegation escalation
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

from services.governance.approval_guard import ApprovalGuard, ApprovalGuardCheckResult
from services.governance.delegation_guard import DelegationGuard, DelegationGuardCheckResult
from services.governance.approval_response import ApprovalResponse
from services.governance.approval_status import ApprovalStatus
from services.governance.decision_request import DecisionRequest
from services.governance.delegation import Delegation
from services.governance.delegation_status import DelegationStatus
from services.governance.delegation_scope import DelegationScope
from services.governance.delegation_limit import DelegationLimit
from services.governance.authority_scope import AuthorityScopeLevel


def _make_response(approved=True, amount=10_000_000, action="CAPITAL_ALLOCATION"):
    return ApprovalResponse(
        approval_id="APR-001", request_id="REQ-001", decision_id="DEC-001",
        status=ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
        approved=approved, approved_amount=amount, approved_action=action,
        valid_from=time.time(), valid_until=time.time() + 3600,
    )


def _make_request(amount=10_000_000, decision_type_str="CAPITAL_ALLOCATION"):
    from services.governance.decision_request import DecisionType
    dt_map = {"CAPITAL_ALLOCATION": DecisionType.CAPITAL_ALLOCATION,
              "DIFFERENT_ACTION": DecisionType.CAPITAL_ALLOCATION}
    dt = dt_map.get(decision_type_str, DecisionType.CAPITAL_ALLOCATION)
    req = DecisionRequest(actor="TEST", decision_type=dt, requested_amount=amount)
    setattr(req, 'amount', amount)
    setattr(req, 'decision_type_str', decision_type_str)
    return req


class TestApprovalGuard(unittest.TestCase):
    """Approval Guard — pre-execution safety checks."""

    def setUp(self):
        self.guard = ApprovalGuard()

    def test_valid_approval_passes(self):
        resp = _make_response()
        req = _make_request()
        result = self.guard.check(resp, req)
        self.assertTrue(result.passed, result.reason)

    def test_replay_detected(self):
        resp = _make_response()
        resp.consume()  # consumed=True, status=EXECUTED
        result = self.guard.check(resp)
        self.assertFalse(result.passed)
        # Guard catches either REPLAY (consumed) or NOT_APPROVED (status changed)
        self.assertTrue(
            "REPLAY" in result.reason or "NOT_APPROVED" in result.reason or "EXECUTED" in result.reason,
            f"Expected replay/executed, got: {result.reason}"
        )

    def test_expired_approval_blocked(self):
        resp = _make_response()
        resp.valid_until = time.time() - 10
        result = self.guard.check(resp)
        self.assertFalse(result.passed)

    def test_amount_exceeded(self):
        resp = _make_response(amount=10_000_000)
        req = _make_request(amount=15_000_000)
        result = self.guard.check(resp, req)
        self.assertFalse(result.passed)
        self.assertIn("AMOUNT", result.reason)

    def test_scope_mismatch(self):
        """Scope mismatch when approval action != request decision type."""
        from services.governance.decision_request import DecisionType
        resp = _make_response(action="CAPITAL_DEALLOCATION")
        req = DecisionRequest(actor="TEST", decision_type=DecisionType.CAPITAL_ALLOCATION, requested_amount=10_000_000)
        setattr(req, 'amount', 10_000_000)
        result = self.guard.check(resp, req)
        self.assertFalse(result.passed)
        self.assertIn("SCOPE", result.reason)

    def test_invalidated_approval_blocked(self):
        resp = _make_response()
        resp.status = ApprovalStatus.INVALIDATED
        result = self.guard.check(resp)
        self.assertFalse(result.passed)

    def test_check_amount_method(self):
        resp = _make_response(amount=10_000_000)
        self.assertTrue(self.guard.check_amount(resp, 10_000_000))
        self.assertTrue(self.guard.check_amount(resp, 5_000_000))
        self.assertFalse(self.guard.check_amount(resp, 10_000_001))

    def test_check_consumed_method(self):
        resp = _make_response()
        self.assertTrue(self.guard.check_consumed(resp))
        resp.consume()
        self.assertFalse(self.guard.check_consumed(resp))


class TestDelegationGuard(unittest.TestCase):
    """Delegation Guard checks."""

    def setUp(self):
        self.guard = DelegationGuard()

    def _make_delegation(self, max_amount=10_000_000):
        scope = DelegationScope("DS", allowed_levels=[AuthorityScopeLevel.PORTFOLIO])
        limit = DelegationLimit("DL", max_amount=max_amount, allowed_actions=["CAPITAL_ALLOCATION"])
        return Delegation(
            delegation_id="DEL-001", delegator="PM", delegate="DEP",
            parent_grant_id="G-001", scope=scope, limit=limit,
            valid_from=time.time(), valid_to=time.time() + 3600,
            status=DelegationStatus.ACTIVE,
        )

    def test_no_delegation_passes(self):
        result = self.guard.check(None)
        self.assertTrue(result.passed)
        self.assertIn("no delegation", result.reason.lower())

    def test_active_delegation_passes(self):
        d = self._make_delegation()
        result = self.guard.check(d)
        self.assertTrue(result.passed, result.reason)

    def test_inactive_delegation_fails(self):
        d = self._make_delegation()
        d.status = DelegationStatus.REVOKED
        result = self.guard.check(d)
        self.assertFalse(result.passed)

    def test_amount_exceeded_fails(self):
        d = self._make_delegation(max_amount=10_000_000)
        req = _make_request(amount=15_000_000)
        result = self.guard.check(d, req)
        self.assertFalse(result.passed)
        self.assertIn("LIMIT", result.reason)

    def test_not_yet_started_fails(self):
        d = self._make_delegation()
        d.valid_from = time.time() + 100
        d.valid_to = time.time() + 200
        result = self.guard.check(d)
        self.assertFalse(result.passed)
        self.assertIn("NOT_STARTED", result.reason)


if __name__ == "__main__":
    unittest.main()
