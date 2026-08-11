"""Tests for ControlResponse factory methods and status mapping."""

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

from services.integration.contracts.control_response import (
    ControlResponse,
    ControlResponseStatus,
)
from services.integration.contracts.control_reason import ReasonCode
from services.integration.contracts.control_evidence import RiskEvidence


class TestControlResponseStatus(unittest.TestCase):

    def test_pass_is_not_terminal(self):
        self.assertFalse(ControlResponseStatus.PASS.is_terminal)
        self.assertTrue(ControlResponseStatus.PASS.is_pass)

    def test_reject_is_terminal(self):
        self.assertTrue(ControlResponseStatus.REJECT.is_terminal)

    def test_block_is_terminal(self):
        self.assertTrue(ControlResponseStatus.BLOCK.is_terminal)

    def test_freeze_is_terminal(self):
        self.assertTrue(ControlResponseStatus.FREEZE.is_terminal)

    def test_status_labels(self):
        self.assertEqual(ControlResponseStatus.PASS.label, "PASS")
        self.assertEqual(ControlResponseStatus.REJECT.label, "REJECT")
        self.assertEqual(ControlResponseStatus.BLOCK.label, "BLOCK")


class TestControlResponseFactories(unittest.TestCase):

    def test_make_pass(self):
        resp = ControlResponse.make_pass(
            domain="risk",
            reason_code=ReasonCode.RISK_CHECK_PASSED,
            flow_id="FLOW-001",
        )
        self.assertEqual(resp.status, ControlResponseStatus.PASS)
        self.assertEqual(resp.reason_code, ReasonCode.RISK_CHECK_PASSED)
        self.assertTrue(resp.passed)

    def test_make_reject(self):
        resp = ControlResponse.make_reject(
            domain="risk",
            reason_code=ReasonCode.RISK_EXPOSURE_BREACH,
            reason="Exposure 18% > limit 15%",
            flow_id="FLOW-001",
        )
        self.assertEqual(resp.status, ControlResponseStatus.REJECT)
        self.assertFalse(resp.passed)
        self.assertIn("Exposure", resp.reason)

    def test_make_block(self):
        resp = ControlResponse.make_block(
            domain="risk",
            reason_code=ReasonCode.RISK_UNKNOWN,
            reason="Risk service unavailable",
            flow_id="FLOW-001",
        )
        self.assertEqual(resp.status, ControlResponseStatus.BLOCK)
        self.assertTrue(resp.is_terminal)

    def test_make_freeze(self):
        resp = ControlResponse.make_freeze(
            domain="governance",
            reason_code=ReasonCode.GOVERNANCE_FROZEN,
            reason="Account frozen",
            flow_id="FLOW-001",
        )
        self.assertEqual(resp.status, ControlResponseStatus.FREEZE)
        self.assertEqual(resp.reason_code, ReasonCode.GOVERNANCE_FROZEN)

    def test_make_expired(self):
        resp = ControlResponse.make_expired(
            domain="approval",
            flow_id="FLOW-001",
        )
        self.assertEqual(resp.status, ControlResponseStatus.EXPIRED)
        self.assertEqual(resp.reason_code, ReasonCode.CONTRACT_EXPIRED)

    def test_make_error(self):
        resp = ControlResponse.make_error(
            domain="risk",
            reason="Internal error",
            flow_id="FLOW-001",
        )
        self.assertEqual(resp.status, ControlResponseStatus.ERROR)
        self.assertEqual(resp.reason_code, ReasonCode.UNKNOWN_ERROR)


class TestControlResponseWithEvidence(unittest.TestCase):

    def test_response_with_risk_evidence(self):
        evidence = RiskEvidence.from_assessment(
            "portfolio_exposure", 0.124, 0.15, evidence_id="EV-001"
        )
        resp = ControlResponse.make_pass(
            domain="risk",
            reason_code=ReasonCode.RISK_LIMIT_OK,
            flow_id="FLOW-001",
            evidence=evidence,
        )
        self.assertIsNotNone(resp.evidence)
        self.assertEqual(resp.evidence.domain, "risk")
        self.assertEqual(resp.evidence.metrics["value"], 0.124)
        self.assertEqual(resp.evidence.metrics["limit"], 0.15)


class TestControlResponseSerialization(unittest.TestCase):

    def test_to_dict(self):
        resp = ControlResponse.make_pass(
            domain="risk",
            reason_code=ReasonCode.RISK_LIMIT_OK,
            flow_id="FLOW-001",
        )
        d = resp.to_dict()
        self.assertEqual(d["domain"], "risk")
        self.assertEqual(d["status"], "PASS")
        self.assertEqual(d["reason_code"], "RISK_LIMIT_OK")


if __name__ == "__main__":
    unittest.main()
