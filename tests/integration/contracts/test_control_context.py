"""Tests for ContractControlContext immutability and integrity."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import uuid
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

from services.integration.contracts.control_context import (
    ContractControlContext,
    IMMUTABLE_CONTEXT_FIELDS,
)
from services.integration.contracts.contract_errors import ContextIntegrityError


class TestContractControlContextCreation(unittest.TestCase):

    def test_auto_generated_flow_id(self):
        ctx = ContractControlContext()
        self.assertIsNotNone(ctx.flow_id)
        self.assertTrue(ctx.flow_id.startswith("FLOW-"))

    def test_explicit_flow_id(self):
        ctx = ContractControlContext(flow_id="FLOW-CUSTOM-001")
        self.assertEqual(ctx.flow_id, "FLOW-CUSTOM-001")

    def test_full_identity(self):
        ctx = ContractControlContext(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            signal_id="SIG-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
            account_id="ACC-001",
        )
        self.assertEqual(ctx.flow_id, "FLOW-001")
        self.assertEqual(ctx.decision_id, "DEC-001")
        self.assertEqual(ctx.strategy_id, "STRAT-001")

    def test_policy_versions(self):
        ctx = ContractControlContext()
        ctx.with_risk_version("RISK-v8")
        ctx.with_governance_version("GOV-v3")
        ctx.with_authority_version("AUTH-v2")
        ctx.with_approval_version("APR-v1")

        self.assertEqual(ctx.risk_version, "RISK-v8")
        self.assertEqual(ctx.governance_version, "GOV-v3")
        self.assertEqual(ctx.authority_version, "AUTH-v2")
        self.assertEqual(ctx.approval_version, "APR-v1")


class TestContextIntegrity(unittest.TestCase):

    def setUp(self):
        self.ctx = ContractControlContext(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
            account_id="ACC-001",
        )

    def test_identical_contexts_pass(self):
        other = ContractControlContext(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
            account_id="ACC-001",
        )
        # Should not raise
        self.ctx.verify_integrity(other)

    def test_different_flow_id_raises(self):
        other = ContractControlContext(
            flow_id="FLOW-002",
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
            account_id="ACC-001",
        )
        with self.assertRaises(ContextIntegrityError) as ctx:
            self.ctx.verify_integrity(other)
        self.assertEqual(ctx.exception.field, "flow_id")

    def test_different_strategy_id_raises(self):
        other = ContractControlContext(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            strategy_id="STRAT-002",
            portfolio_id="PORT-001",
            account_id="ACC-001",
        )
        with self.assertRaises(ContextIntegrityError) as ctx:
            self.ctx.verify_integrity(other)
        self.assertEqual(ctx.exception.field, "strategy_id")

    def test_empty_flow_id_self_check_raises(self):
        ctx = ContractControlContext(flow_id="")
        with self.assertRaises(ContextIntegrityError):
            ctx.verify_self_consistent()

    def test_partially_empty_context_does_not_raise(self):
        """A context with only some fields set shouldn't raise when
        the other context has different values for empty fields."""
        ctx = ContractControlContext(flow_id="FLOW-001")
        other = ContractControlContext(flow_id="FLOW-001", decision_id="DEC-002")
        # decision_id is empty in ctx → no integrity check triggered
        ctx.verify_integrity(other)

    def test_immutable_fields_tuple(self):
        """Verify the known immutable fields."""
        self.assertIn("flow_id", IMMUTABLE_CONTEXT_FIELDS)
        self.assertIn("decision_id", IMMUTABLE_CONTEXT_FIELDS)
        self.assertIn("strategy_id", IMMUTABLE_CONTEXT_FIELDS)
        self.assertIn("portfolio_id", IMMUTABLE_CONTEXT_FIELDS)
        self.assertIn("account_id", IMMUTABLE_CONTEXT_FIELDS)


class TestContextVersionTracking(unittest.TestCase):

    def test_chained_version_setters(self):
        ctx = ContractControlContext()
        result = (
            ctx.with_risk_version("v1")
            .with_governance_version("v2")
            .with_authority_version("v3")
            .with_approval_version("v4")
            .with_policy_version("v5")
        )
        self.assertIs(result, ctx)
        self.assertEqual(ctx.risk_version, "v1")
        self.assertEqual(ctx.policy_version, "v5")


if __name__ == "__main__":
    unittest.main()
