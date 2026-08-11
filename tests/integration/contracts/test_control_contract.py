"""Tests for ControlContract creation and lifecycle."""

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

from services.integration.contracts.control_contract import ControlContract
from services.integration.contracts.control_request import ControlRequest, RiskRequest
from services.integration.contracts.control_context import ContractControlContext
from services.integration.contracts.control_response import ControlResponse, ControlResponseStatus
from services.integration.contracts.control_reason import ReasonCode
from services.integration.contracts.control_decision import ControlDecision, DecisionStatus
from services.integration.contracts.control_constraint import (
    ControlConstraint, ConstraintSource, ConstraintType, ConstraintRule,
)
from services.integration.contracts.control_evidence import RiskEvidence
from services.integration.contracts.control_reference import ControlReference


class TestControlContractCreation(unittest.TestCase):

    def test_create_minimal_contract(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        self.assertIsNotNone(contract.contract_id)
        self.assertTrue(contract.contract_id.startswith("CTR-"))
        self.assertEqual(contract.domain, "risk")
        self.assertEqual(contract.contract_version, "v1")
        self.assertFalse(contract.is_executed)
        self.assertFalse(contract.is_decided)

    def test_create_with_custom_version(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="governance", context=ctx)
        contract = ControlContract.create(domain="governance", request=req, version="v2")

        self.assertEqual(contract.contract_version, "v2")

    def test_contract_with_response(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        resp = ControlResponse.make_pass(
            domain="risk",
            reason_code=ReasonCode.RISK_CHECK_PASSED,
            flow_id=ctx.flow_id,
        )
        contract.with_response(resp)

        self.assertTrue(contract.is_executed)
        self.assertTrue(contract.passed)

    def test_contract_with_decision(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        resp = ControlResponse.make_pass("risk", ReasonCode.RISK_CHECK_PASSED, flow_id=ctx.flow_id)
        decision = ControlDecision.from_responses(
            flow_id=ctx.flow_id,
            responses=[resp],
        )
        contract.with_response(resp).with_decision(decision)

        self.assertTrue(contract.is_decided)
        self.assertTrue(contract.decision.allowed)

    def test_contract_with_constraints_and_evidence(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        c = ControlConstraint.max_notional(
            10_000_000, ConstraintSource.RISK, policy_version="RISK-v8", rule_id="RISK-001"
        )
        e = RiskEvidence.from_assessment("exposure", 0.12, 0.15)

        contract.add_constraint(c).add_evidence(e)

        self.assertEqual(len(contract.constraints), 1)
        self.assertEqual(len(contract.evidence), 1)

    def test_contract_with_reference(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        ref = ControlReference.root(flow_id=ctx.flow_id, domain="signal")
        contract.add_reference(ref)

        self.assertEqual(len(contract.references), 1)
        self.assertTrue(contract.references[0].is_root)


class TestControlContractExpiry(unittest.TestCase):

    def test_contract_not_expired_by_default(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        self.assertFalse(contract.is_expired)

    def test_contract_with_future_expiry(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.with_expiry(time.time() + 3600)

        self.assertFalse(contract.is_expired)

    def test_contract_with_past_expiry(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.with_expiry(time.time() - 1)

        self.assertTrue(contract.is_expired)


class TestControlContractSummary(unittest.TestCase):

    def test_summary_contains_key_fields(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)

        s = contract.summary
        self.assertIn("contract_id", s)
        self.assertIn("version", s)
        self.assertIn("domain", s)
        self.assertIn("flow_id", s)
        self.assertIn("is_expired", s)
        self.assertIn("is_executed", s)
        self.assertIn("passed", s)


class TestControlContractTags(unittest.TestCase):

    def test_contract_tags(self):
        ctx = ContractControlContext()
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.with_tag("env", "prod").with_tag("region", "us-east")

        self.assertEqual(contract.tags["env"], "prod")
        self.assertEqual(contract.tags["region"], "us-east")


if __name__ == "__main__":
    unittest.main()
