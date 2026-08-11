"""Tests for domain-specific evidence types and factory methods."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import time
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

from services.integration.contracts.control_evidence import (
    ControlEvidence,
    RiskEvidence,
    GovernanceEvidence,
    AuthorityEvidence,
    ApprovalEvidence,
)


class TestControlEvidence(unittest.TestCase):

    def test_base_evidence_creation(self):
        e = ControlEvidence(
            evidence_id="EV-001",
            domain="risk",
            metrics={"key": "value"},
            tags={"type": "test"},
        )
        self.assertEqual(e.evidence_id, "EV-001")
        self.assertEqual(e.domain, "risk")
        self.assertEqual(e.metrics["key"], "value")

    def test_to_dict(self):
        e = ControlEvidence(evidence_id="EV-001", domain="risk")
        d = e.to_dict()
        self.assertEqual(d["evidence_id"], "EV-001")
        self.assertEqual(d["domain"], "risk")


class TestRiskEvidence(unittest.TestCase):

    def test_default_domain(self):
        e = RiskEvidence()
        self.assertEqual(e.domain, "risk")

    def test_from_assessment(self):
        e = RiskEvidence.from_assessment(
            metric="portfolio_exposure",
            value=0.124,
            limit=0.15,
            threshold_percent=100.0,
        )
        self.assertEqual(e.domain, "risk")
        self.assertEqual(e.metrics["metric"], "portfolio_exposure")
        self.assertEqual(e.metrics["value"], 0.124)
        self.assertEqual(e.metrics["limit"], 0.15)
        self.assertGreater(e.evaluated_at, 0)

    def test_from_assessment_with_extra(self):
        e = RiskEvidence.from_assessment(
            metric="var",
            value=0.05,
            limit=0.07,
            extra_metrics={"var_95": 0.04},
            extra_tags={"model": "historical"},
        )
        self.assertEqual(e.metrics["var_95"], 0.04)
        self.assertEqual(e.tags["model"], "historical")


class TestGovernanceEvidence(unittest.TestCase):

    def test_default_domain(self):
        e = GovernanceEvidence()
        self.assertEqual(e.domain, "governance")

    def test_from_policy_eval(self):
        e = GovernanceEvidence.from_policy_eval(
            governance_state="NORMAL",
            policy_name="RISK_POLICY",
            policy_version="v8",
            policy_hash="abc123",
        )
        self.assertEqual(e.metrics["governance_state"], "NORMAL")
        self.assertEqual(e.metrics["policy_name"], "RISK_POLICY")
        self.assertEqual(e.metrics["policy_version"], "v8")
        self.assertEqual(e.metrics["policy_hash"], "abc123")


class TestAuthorityEvidence(unittest.TestCase):

    def test_default_domain(self):
        e = AuthorityEvidence()
        self.assertEqual(e.domain, "authority")

    def test_from_authorization(self):
        e = AuthorityEvidence.from_authorization(
            authority_limit=20_000_000,
            requested_notional=12_000_000,
            remaining_limit=8_000_000,
            authority_status="VALID",
        )
        self.assertEqual(e.metrics["authority_limit"], 20_000_000)
        self.assertEqual(e.metrics["requested_notional"], 12_000_000)
        self.assertEqual(e.metrics["remaining_limit"], 8_000_000)
        self.assertEqual(e.metrics["authority_status"], "VALID")


class TestApprovalEvidence(unittest.TestCase):

    def test_default_domain(self):
        e = ApprovalEvidence()
        self.assertEqual(e.domain, "approval")

    def test_from_approval(self):
        e = ApprovalEvidence.from_approval(
            approval_id="APR-20260811-001",
            approved_notional=15_000_000,
            requested_notional=12_000_000,
            expires_at=time.time() + 3600,
            scope="PORTFOLIO_A",
        )
        self.assertEqual(e.metrics["approval_id"], "APR-20260811-001")
        self.assertEqual(e.metrics["approved_notional"], 15_000_000)
        self.assertEqual(e.metrics["scope"], "PORTFOLIO_A")


if __name__ == "__main__":
    unittest.main()
