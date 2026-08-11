"""Tests for ContractValidator — structural and semantic validation."""

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
from services.integration.contracts.control_request import ControlRequest
from services.integration.contracts.control_context import ContractControlContext
from services.integration.contracts.control_constraint import (
    ControlConstraint, ConstraintSource,
)
from services.integration.contracts.control_reference import ControlReference
from services.integration.contract_validator import ContractValidator


class TestContractValidatorIdentity(unittest.TestCase):

    def setUp(self):
        self.validator = ContractValidator()
        self.ctx = ContractControlContext(flow_id="FLOW-001")
        self.req = ControlRequest(domain="risk", context=self.ctx)

    def test_valid_contract_passes(self):
        contract = ControlContract.create(domain="risk", request=self.req)
        result = self.validator.validate(contract)
        self.assertTrue(result.valid, f"Errors: {result.errors}")

    def test_empty_contract_id_fails(self):
        contract = ControlContract.create(domain="risk", request=self.req)
        contract.contract_id = ""
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "contract_id" for e in result.errors))

    def test_empty_version_fails(self):
        contract = ControlContract.create(domain="risk", request=self.req)
        contract.contract_version = ""
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "contract_version" for e in result.errors))

    def test_invalid_version_format_fails(self):
        contract = ControlContract.create(domain="risk", request=self.req)
        contract.contract_version = "not-a-version"
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "contract_version" for e in result.errors))


class TestContractValidatorDomain(unittest.TestCase):

    def setUp(self):
        self.validator = ContractValidator()
        self.ctx = ContractControlContext(flow_id="FLOW-001")

    def test_empty_domain_fails(self):
        req = ControlRequest(domain="", context=self.ctx)
        contract = ControlContract.create(domain="", request=req)
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "domain" for e in result.errors))

    def test_unknown_domain_warns(self):
        req = ControlRequest(domain="billing", context=self.ctx)
        contract = ControlContract.create(domain="billing", request=req)
        result = self.validator.validate(contract)
        self.assertTrue(result.valid)  # unknown domain is a warning, not error
        self.assertTrue(any("Unknown domain" in w["message"] for w in result.warnings))

    def test_known_domains_pass(self):
        for domain in ["risk", "governance", "authority", "approval", "admission"]:
            req = ControlRequest(domain=domain, context=self.ctx)
            contract = ControlContract.create(domain=domain, request=req)
            result = self.validator.validate(contract)
            self.assertTrue(result.valid, f"Domain '{domain}' should pass")


class TestContractValidatorContext(unittest.TestCase):

    def setUp(self):
        self.validator = ContractValidator()

    def test_empty_flow_id_fails(self):
        ctx = ContractControlContext(flow_id="")
        req = ControlRequest(domain="risk", context=ctx)
        contract = ControlContract.create(domain="risk", request=req)
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "context.flow_id" for e in result.errors))


class TestContractValidatorExpiry(unittest.TestCase):

    def setUp(self):
        self.validator = ContractValidator()
        self.ctx = ContractControlContext(flow_id="FLOW-001")

    def test_expired_contract_fails(self):
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.with_expiry(time.time() - 1)
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "expires_at" for e in result.errors))

    def test_expired_request_ttl_fails(self):
        req = ControlRequest(domain="risk", context=self.ctx, ttl_seconds=-1)
        contract = ControlContract.create(domain="risk", request=req)
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)
        self.assertTrue(any(e["field"] == "request.ttl_seconds" for e in result.errors))


class TestContractValidatorReferences(unittest.TestCase):

    def setUp(self):
        self.validator = ContractValidator()
        self.ctx = ContractControlContext(flow_id="FLOW-001")

    def test_orphan_reference_fails(self):
        ref = ControlReference(domain="risk", flow_id="FLOW-001", parent_reference_id="REF-NONEXISTENT")
        req = ControlRequest(domain="risk", context=self.ctx)
        contract = ControlContract.create(domain="risk", request=req)
        contract.add_reference(ref)
        result = self.validator.validate(contract)
        self.assertFalse(result.valid)


class TestValidationResult(unittest.TestCase):

    def test_valid_by_default(self):
        from services.integration.contract_validator import ValidationResult
        r = ValidationResult()
        self.assertTrue(r.valid)
        self.assertEqual(len(r.errors), 0)
        self.assertEqual(len(r.warnings), 0)

    def test_add_error_sets_invalid(self):
        from services.integration.contract_validator import ValidationResult
        r = ValidationResult()
        r.add_error("field", "message")
        self.assertFalse(r.valid)
        self.assertEqual(len(r.errors), 1)


if __name__ == "__main__":
    unittest.main()
