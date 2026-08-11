"""Tests for ControlConstraint intersection, conflict, and provenance."""

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

from services.integration.contracts.control_constraint import (
    ControlConstraint,
    ConstraintType,
    ConstraintRule,
    ConstraintSource,
    EffectiveConstraints,
    intersect_constraints,
)
from services.integration.contracts.contract_errors import ConstraintConflictError


class TestControlConstraintCreation(unittest.TestCase):

    def test_max_notional_factory(self):
        c = ControlConstraint.max_notional(
            10_000_000,
            ConstraintSource.RISK,
            policy_version="RISK-v8",
            rule_id="RISK-EXPOSURE-004",
        )
        self.assertEqual(c.constraint_type, ConstraintType.MAX_NOTIONAL)
        self.assertEqual(c.rule, ConstraintRule.MAX)
        self.assertEqual(c.numeric_value, 10_000_000)
        self.assertEqual(c.source, ConstraintSource.RISK)
        self.assertEqual(c.policy_version, "RISK-v8")
        self.assertEqual(c.rule_id, "RISK-EXPOSURE-004")

    def test_allowed_symbols_factory(self):
        c = ControlConstraint.allowed_symbols(
            {"AAPL", "GOOGL", "MSFT"},
            ConstraintSource.GOVERNANCE,
            rule_id="GOV-SYMBOL-001",
        )
        self.assertEqual(c.constraint_type, ConstraintType.ALLOWED_SYMBOLS)
        self.assertEqual(c.rule, ConstraintRule.ALLOW)
        self.assertIsNotNone(c.set_value)
        self.assertEqual(c.set_value, {"AAPL", "GOOGL", "MSFT"})

    def test_deny_symbols_factory(self):
        c = ControlConstraint.deny_symbols(
            {"TSLA"},
            ConstraintSource.GOVERNANCE,
        )
        self.assertEqual(c.rule, ConstraintRule.DENY)
        self.assertEqual(c.set_value, {"TSLA"})


class TestConstraintIntersection(unittest.TestCase):

    def test_single_constraint_passthrough(self):
        constraints = [
            ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK),
        ]
        result = intersect_constraints(constraints)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(len(result.constraints), 1)
        self.assertEqual(result.constraints[0].numeric_value, 10_000_000)

    def test_max_notional_takes_minimum(self):
        constraints = [
            ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK),
            ControlConstraint.max_notional(15_000_000, ConstraintSource.GOVERNANCE),
            ControlConstraint.max_notional(20_000_000, ConstraintSource.AUTHORITY),
        ]
        result = intersect_constraints(constraints)
        effective = result.get_numeric(ConstraintType.MAX_NOTIONAL)
        self.assertEqual(effective, 10_000_000)

    def test_max_exposure_takes_minimum(self):
        constraints = [
            ControlConstraint.max_exposure(0.25, ConstraintSource.RISK),
            ControlConstraint.max_exposure(0.30, ConstraintSource.GOVERNANCE),
        ]
        result = intersect_constraints(constraints)
        self.assertEqual(result.get_numeric(ConstraintType.MAX_EXPOSURE), 0.25)

    def test_max_leverage_takes_minimum(self):
        constraints = [
            ControlConstraint.max_leverage(3.0, ConstraintSource.RISK),
            ControlConstraint.max_leverage(5.0, ConstraintSource.AUTHORITY),
        ]
        result = intersect_constraints(constraints)
        self.assertEqual(result.get_numeric(ConstraintType.MAX_LEVERAGE), 3.0)

    def test_allowed_symbols_takes_intersection(self):
        constraints = [
            ControlConstraint.allowed_symbols({"AAPL", "GOOGL", "MSFT"}, ConstraintSource.RISK),
            ControlConstraint.allowed_symbols({"AAPL", "GOOGL", "TSLA"}, ConstraintSource.GOVERNANCE),
        ]
        result = intersect_constraints(constraints)
        allowed = result.get_set(ConstraintType.ALLOWED_SYMBOLS)
        self.assertEqual(allowed, {"AAPL", "GOOGL"})

    def test_deny_removes_from_allow(self):
        constraints = [
            ControlConstraint.allowed_symbols({"AAPL", "GOOGL", "TSLA"}, ConstraintSource.RISK),
            ControlConstraint.deny_symbols({"TSLA"}, ConstraintSource.GOVERNANCE),
        ]
        result = intersect_constraints(constraints)
        allowed = result.get_set(ConstraintType.ALLOWED_SYMBOLS)
        self.assertEqual(allowed, {"AAPL", "GOOGL"})

    def test_deny_removes_all_triggers_conflict(self):
        constraints = [
            ControlConstraint.allowed_symbols({"TSLA"}, ConstraintSource.RISK),
            ControlConstraint.deny_symbols({"TSLA"}, ConstraintSource.GOVERNANCE),
        ]
        with self.assertRaises(ConstraintConflictError):
            intersect_constraints(constraints)

    def test_empty_input(self):
        result = intersect_constraints([])
        self.assertEqual(len(result.constraints), 0)

    def test_mixed_constraint_types(self):
        constraints = [
            ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK),
            ControlConstraint.max_notional(12_000_000, ConstraintSource.AUTHORITY),
            ControlConstraint.max_exposure(0.15, ConstraintSource.RISK),
            ControlConstraint.allowed_symbols({"AAPL", "GOOGL"}, ConstraintSource.RISK),
            ControlConstraint.allowed_symbols({"GOOGL"}, ConstraintSource.GOVERNANCE),
        ]
        result = intersect_constraints(constraints)

        # MAX_NOTIONAL = min(10M, 12M) = 10M (from Risk)
        self.assertEqual(result.get_numeric(ConstraintType.MAX_NOTIONAL), 10_000_000)
        # MAX_EXPOSURE = 0.15
        self.assertEqual(result.get_numeric(ConstraintType.MAX_EXPOSURE), 0.15)
        # ALLOWED_SYMBOLS = {"AAPL","GOOGL"} ∩ {"GOOGL"} = {"GOOGL"}
        self.assertEqual(result.get_set(ConstraintType.ALLOWED_SYMBOLS), {"GOOGL"})


class TestConstraintProvenance(unittest.TestCase):

    def test_constraint_carries_source(self):
        c = ControlConstraint.max_notional(
            5_000_000,
            ConstraintSource.RISK,
            policy_version="RISK-v8",
            rule_id="RISK-EXPOSURE-004",
        )
        self.assertEqual(c.source, ConstraintSource.RISK)
        self.assertEqual(c.policy_version, "RISK-v8")
        self.assertEqual(c.rule_id, "RISK-EXPOSURE-004")

    def test_constraint_source_labels(self):
        self.assertEqual(ConstraintSource.RISK.label, "RISK")
        self.assertEqual(ConstraintSource.GOVERNANCE.label, "GOVERNANCE")
        self.assertEqual(ConstraintSource.AUTHORITY.label, "AUTHORITY")

    def test_intersection_preserves_tightest_source(self):
        """The resulting constraint should reference the tightest source."""
        constraints = [
            ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK,
                                           policy_version="RISK-v8", rule_id="RISK-001"),
            ControlConstraint.max_notional(20_000_000, ConstraintSource.AUTHORITY,
                                           policy_version="AUTH-v2", rule_id="AUTH-001"),
        ]
        result = intersect_constraints(constraints)
        c = result.get(ConstraintType.MAX_NOTIONAL)
        self.assertEqual(c.source, ConstraintSource.RISK)
        self.assertEqual(c.policy_version, "RISK-v8")

    def test_deny_only_triggers_conflict_warning(self):
        constraints = [
            ControlConstraint.deny_symbols({"FORBIDDEN"}, ConstraintSource.GOVERNANCE),
        ]
        result = intersect_constraints(constraints)
        self.assertTrue(result.has_conflicts)
        self.assertIn("FORBIDDEN", result.conflicts[0])


class TestConstraintExpiry(unittest.TestCase):

    def test_constraint_not_expired_by_default(self):
        c = ControlConstraint.max_notional(10_000_000, ConstraintSource.RISK)
        self.assertFalse(c.is_expired)

    def test_constraint_expired(self):
        import time
        c = ControlConstraint.max_notional(
            10_000_000, ConstraintSource.RISK, expires_at=time.time() - 1
        )
        self.assertTrue(c.is_expired)


if __name__ == "__main__":
    unittest.main()
