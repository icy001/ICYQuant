"""Tests for domain-specific request types and conversion to ControlRequest."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest

# ── Virtual package bootstrap ──────────────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc

_svc_dir = os.path.join(_ws, "services")
_int_dir = os.path.join(_svc_dir, "integration")
_ctr_dir = os.path.join(_int_dir, "contracts")

if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod

if "services.integration.contracts" not in sys.modules:
    _pkg = types.ModuleType("services.integration.contracts")
    _pkg.__path__ = [_ctr_dir]
    sys.modules["services.integration.contracts"] = _pkg

for _dir, _pkg_name, _names in [
    (_ctr_dir, "services.integration.contracts", [
        "contract_errors", "control_version", "control_reason",
        "control_context", "control_request", "control_response",
        "control_evidence", "control_constraint", "control_reference",
        "control_decision", "control_contract",
    ]),
    (_int_dir, "services.integration", [
        "contract_registry", "contract_validator", "contract_serializer",
        "contract_fingerprint", "contract_metrics",
    ]),
]:
    for _name in _names:
        _fp = os.path.join(_dir, f"{_name}.py")
        if not os.path.exists(_fp):
            continue
        _spec = importlib.util.spec_from_file_location(f"{_pkg_name}.{_name}", _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[f"{_pkg_name}.{_name}"] = _m
        _spec.loader.exec_module(_m)

from services.integration.contracts.control_request import (
    ControlRequest,
    RiskRequest,
    GovernanceRequest,
    AuthorityRequest,
    ApprovalRequest,
)
from services.integration.contracts.control_context import ContractControlContext


class TestControlRequest(unittest.TestCase):
    """Unified control request envelope."""

    def setUp(self):
        self.ctx = ContractControlContext(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
            account_id="ACC-001",
        )

    def test_create_generic_request(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        self.assertTrue(req.request_id.startswith("REQ-"))
        self.assertEqual(req.domain, "risk")
        self.assertEqual(req.context.flow_id, "FLOW-001")

    def test_request_ttl_default(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        self.assertFalse(req.is_expired)

    def test_request_ttl_expired(self):
        req = ControlRequest(domain="risk", context=self.ctx, ttl_seconds=-1)
        self.assertTrue(req.is_expired)

    def test_to_dict(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        d = req.to_dict()
        self.assertEqual(d["domain"], "risk")
        self.assertIn("context", d)


class TestRiskRequest(unittest.TestCase):

    def setUp(self):
        self.ctx = ContractControlContext(flow_id="FLOW-001")
        self.req = RiskRequest(
            context=self.ctx,
            symbol="AAPL",
            side="BUY",
            quantity=1000,
            notional=150_000,
            order_type="LIMIT",
            risk_data={"exposure": 0.3},
        )

    def test_create_risk_request(self):
        self.assertTrue(self.req.request_id.startswith("RISK-"))
        self.assertEqual(self.req.symbol, "AAPL")
        self.assertEqual(self.req.side, "BUY")

    def test_convert_to_control_request(self):
        creq = self.req.to_control_request()
        self.assertEqual(creq.domain, "risk")
        self.assertEqual(creq.payload["symbol"], "AAPL")
        self.assertEqual(creq.payload["quantity"], 1000)


class TestGovernanceRequest(unittest.TestCase):

    def setUp(self):
        self.ctx = ContractControlContext(flow_id="FLOW-002")
        self.req = GovernanceRequest(
            context=self.ctx,
            policy_name="RISK_POLICY",
            policy_version="v8",
            governance_data={"state": "NORMAL"},
        )

    def test_create_governance_request(self):
        self.assertTrue(self.req.request_id.startswith("GOV-"))
        self.assertEqual(self.req.policy_name, "RISK_POLICY")

    def test_convert_to_control_request(self):
        creq = self.req.to_control_request()
        self.assertEqual(creq.domain, "governance")
        self.assertEqual(creq.payload["policy_name"], "RISK_POLICY")


class TestAuthorityRequest(unittest.TestCase):

    def setUp(self):
        self.ctx = ContractControlContext(flow_id="FLOW-003")
        self.req = AuthorityRequest(
            context=self.ctx,
            trader_id="TRADER-001",
            requested_notional=12_000_000,
            authority_data={"limit": 20_000_000},
        )

    def test_create_authority_request(self):
        self.assertTrue(self.req.request_id.startswith("AUTH-"))
        self.assertEqual(self.req.trader_id, "TRADER-001")
        self.assertEqual(self.req.requested_notional, 12_000_000)

    def test_convert_to_control_request(self):
        creq = self.req.to_control_request()
        self.assertEqual(creq.domain, "authority")
        self.assertEqual(creq.payload["requested_notional"], 12_000_000)


class TestApprovalRequest(unittest.TestCase):

    def setUp(self):
        self.ctx = ContractControlContext(flow_id="FLOW-004")
        self.req = ApprovalRequest(
            context=self.ctx,
            approval_id="APR-20260811-001",
            requested_notional=12_000_000,
            scope="PORTFOLIO_A",
        )

    def test_create_approval_request(self):
        self.assertTrue(self.req.request_id.startswith("APR-"))
        self.assertEqual(self.req.scope, "PORTFOLIO_A")

    def test_convert_to_control_request(self):
        creq = self.req.to_control_request()
        self.assertEqual(creq.domain, "approval")
        self.assertEqual(creq.payload["approval_id"], "APR-20260811-001")


if __name__ == "__main__":
    unittest.main()
