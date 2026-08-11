"""
Tests for policy_conflict_detector.py — Conflict detection between policies.

Covers spec test requirements:
  - Conflict: compatible, overlapping, contradictory, impossible
"""

import sys
import os
import unittest
import types
import importlib.util

# --- Setup virtual package hierarchy ---
_gov_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_services_dir = os.path.dirname(_gov_dir)
_project_root = os.path.dirname(_services_dir)
sys.path.insert(0, _project_root)

_svc = types.ModuleType("services")
_svc.__path__ = [_services_dir]; _svc.__package__ = "services"
sys.modules["services"] = _svc

_gov = types.ModuleType("services.governance")
_gov.__path__ = [_gov_dir]; _gov.__package__ = "services.governance"
sys.modules["services.governance"] = _gov

_gov_init_spec = importlib.util.spec_from_file_location(
    "services.governance.__init__",
    os.path.join(_gov_dir, "__init__.py"),
    submodule_search_locations=[_gov_dir],
)
_gov_loader = importlib.util.module_from_spec(_gov_init_spec)
sys.modules["services.governance"] = _gov_loader
_gov_init_spec.loader.exec_module(_gov_loader)

from services.governance.policy_conflict_detector import (
    PolicyConflictDetector,
    PolicyConflict,
    ConflictType,
    ConflictSeverity,
)
from services.governance.policy_rule import PolicyRule
from services.governance.policy_version import PolicyVersion
from services.governance.policy_registry import PolicyRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_version(policy_id, rules, scope="GLOBAL"):
    v = PolicyVersion(policy_id=policy_id, version="1.0.0", name=policy_id, scope=scope)
    for r in rules:
        v.add_rule(r)
    v.validate("tester")
    v.approve("tester")
    v.publish("tester")
    v.activate("tester")
    return v


# ---------------------------------------------------------------------------
# PolicyConflict data model tests (no registry needed)
# ---------------------------------------------------------------------------

class TestPolicyConflictDataModel(unittest.TestCase):
    """Test PolicyConflict creation and properties (unit-level, no registry)."""

    def test_conflict_is_blocking(self):
        c = PolicyConflict(
            conflict_id="CF-01",
            conflict_type=ConflictType.DIRECT_CONTRADICTION,
            severity=ConflictSeverity.CRITICAL,
            policy_a="POL-A", version_a="1.0.0",
            policy_b="POL-B", version_b="1.0.0",
        )
        self.assertTrue(c.is_blocking)

    def test_conflict_not_blocking_low(self):
        c = PolicyConflict(
            conflict_id="CF-02",
            conflict_type=ConflictType.SCOPE_OVERLAP,
            severity=ConflictSeverity.LOW,
            policy_a="POL-A", version_a="1.0.0",
            policy_b="POL-B", version_b="1.0.0",
        )
        self.assertFalse(c.is_blocking)
        self.assertFalse(c.is_resolved)

    def test_conflict_resolution(self):
        c = PolicyConflict(
            conflict_id="CF-03",
            conflict_type=ConflictType.SCOPE_OVERLAP,
            severity=ConflictSeverity.MEDIUM,
            policy_a="POL-A", version_a="1.0.0",
            policy_b="POL-B", version_b="1.0.0",
            description="Overlapping scope conflict",
        )
        self.assertFalse(c.is_resolved)
        c.resolve("Manual override: Policy B takes precedence", "admin")
        self.assertTrue(c.is_resolved)
        self.assertIsNotNone(c.resolved_at)

    def test_to_dict(self):
        c = PolicyConflict(
            conflict_id="CF-04",
            conflict_type=ConflictType.DIRECT_CONTRADICTION,
            severity=ConflictSeverity.HIGH,
            policy_a="POL-A", version_a="2.0.0",
            policy_b="POL-B", version_b="1.0.0",
            description="Cannot satisfy both constraints",
            conflicting_rules=["R1", "R2"],
        )
        d = c.to_dict()
        self.assertEqual(d["conflict_id"], "CF-04")
        self.assertEqual(d["conflict_type"], "DIRECT_CONTRADICTION")
        self.assertTrue(d["is_blocking"])
        self.assertIn("R1", d["conflicting_rules"])

    def test_from_dict_roundtrip(self):
        original = PolicyConflict(
            conflict_id="CF-05",
            conflict_type=ConflictType.VERSION_CONFLICT,
            severity=ConflictSeverity.CRITICAL,
            policy_a="POL-MULTI", version_a="1.0.0",
            policy_b="POL-MULTI", version_b="2.0.0",
        )
        restored = PolicyConflict.from_dict(original.to_dict())
        self.assertEqual(restored.conflict_id, original.conflict_id)
        self.assertEqual(restored.conflict_type, original.conflict_type)


# ---------------------------------------------------------------------------
# Contradiction detection helpers
# ---------------------------------------------------------------------------

class TestContradictionLogic(unittest.TestCase):
    """Test _find_contradictions static method."""

    def test_opposite_operators_contradict(self):
        """v1 says >30%, v2 says <20% — contradictory."""
        v1 = PolicyVersion(policy_id="POL-A", version="1.0.0", name="A")
        v1.add_rule(PolicyRule(rule_id="R1", metric="alloc", operator=">", threshold=30.0))
        v2 = PolicyVersion(policy_id="POL-B", version="1.0.0", name="B")
        v2.add_rule(PolicyRule(rule_id="R2", metric="alloc", operator="<", threshold=20.0))

        results = PolicyConflictDetector._find_contradictions(v1, v2)
        self.assertGreater(len(results), 0)

    def test_same_direction_no_contradiction(self):
        """Both say '<=' — not contradictory (stricter constraint compatible)."""
        v1 = PolicyVersion(policy_id="POL-A", version="1.0.0", name="A")
        v1.add_rule(PolicyRule(rule_id="R1", metric="leverage", operator="<=", threshold=3.0))
        v2 = PolicyVersion(policy_id="POL-B", version="1.0.0", name="B")
        v2.add_rule(PolicyRule(rule_id="R2", metric="leverage", operator="<=", threshold=2.0))

        results = PolicyConflictDetector._find_contradictions(v1, v2)
        self.assertEqual(len(results), 0)

    def test_different_metrics_no_contradiction(self):
        """Different metrics — no contradiction."""
        v1 = PolicyVersion(policy_id="POL-A", version="1.0.0", name="A")
        v1.add_rule(PolicyRule(rule_id="R1", metric="leverage", operator=">", threshold=5.0))
        v2 = PolicyVersion(policy_id="POL-B", version="1.0.0", name="B")
        v2.add_rule(PolicyRule(rule_id="R2", metric="drawdown", operator="<", threshold=0.02))

        results = PolicyConflictDetector._find_contradictions(v1, v2)
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# Conflict detection via registry
# ---------------------------------------------------------------------------

class TestConflictDetectionWithRegistry(unittest.TestCase):
    """Test conflict detection using PolicyRegistry."""

    def setUp(self):
        self.registry = PolicyRegistry()
        self.detector = PolicyConflictDetector(registry=self.registry)

    def _register_active(self, v):
        self.registry.register(v)
        self.registry.set_active(v.policy_id, v.version_id)

    def test_no_conflicts_empty_registry(self):
        """Empty registry → no conflicts."""
        conflicts = self.detector.detect_all()
        self.assertEqual(len(conflicts), 0)

    def test_detect_scope_overlap(self):
        """Two active policies with overlapping scopes → scope overlap conflict."""
        v1 = _make_version("POL-A", [
            PolicyRule(rule_id="R1", metric="leverage", operator="<=", threshold=3.0),
        ], scope="PORTFOLIO")
        v2 = _make_version("POL-B", [
            PolicyRule(rule_id="R2", metric="drawdown", operator="<=", threshold=0.10),
        ], scope="PORTFOLIO")

        self._register_active(v1)
        self._register_active(v2)

        conflicts = self.detector.detect_all()
        self.assertGreater(len(conflicts), 0)

    def test_detect_direct_contradiction(self):
        """Conflicting rules on same metric → DIRECT_CONTRADICTION."""
        v1 = _make_version("POL-A", [
            PolicyRule(rule_id="R1", metric="allocation", operator=">", threshold=30.0),
        ])
        v2 = _make_version("POL-B", [
            PolicyRule(rule_id="R2", metric="allocation", operator="<", threshold=20.0),
        ])

        self._register_active(v1)
        self._register_active(v2)

        conflicts = self.detector.detect_all()
        contradictions = [c for c in conflicts
                          if c.conflict_type == ConflictType.DIRECT_CONTRADICTION]
        self.assertGreater(len(contradictions), 0)

    def test_self_contradiction_via_detect_for_version(self):
        """detect_for_version catches contradictions with active policies."""
        v_active = _make_version("POL-X", [
            PolicyRule(rule_id="R1", metric="exposure", operator=">", threshold=50.0),
        ])
        self._register_active(v_active)

        v_new = _make_version("POL-Y", [
            PolicyRule(rule_id="R2", metric="exposure", operator="<", threshold=10.0),
        ])

        conflicts = self.detector.detect_for_version(v_new)
        self.assertGreater(len(conflicts), 0)


# ---------------------------------------------------------------------------
# Conflict queries
# ---------------------------------------------------------------------------

class TestConflictQueries(unittest.TestCase):
    """Test conflict query methods."""

    def setUp(self):
        self.registry = PolicyRegistry()
        self.detector = PolicyConflictDetector(registry=self.registry)

    def _register_active(self, v):
        self.registry.register(v)
        self.registry.set_active(v.policy_id, v.version_id)

    def test_get_blocking_returns_critical(self):
        """get_blocking returns unresolved blocking conflicts."""
        v1 = _make_version("POL-C1", [
            PolicyRule(rule_id="R1", metric="cap", operator=">", threshold=100.0),
        ])
        v2 = _make_version("POL-C2", [
            PolicyRule(rule_id="R2", metric="cap", operator="<", threshold=50.0),
        ])
        self._register_active(v1)
        self._register_active(v2)
        self.detector.detect_all()
        blocking = self.detector.get_blocking()
        self.assertGreater(len(blocking), 0)

    def test_has_blocking_conflicts(self):
        v1 = _make_version("POL-AA", [
            PolicyRule(rule_id="R1", metric="x", operator=">", threshold=10.0),
        ])
        v2 = _make_version("POL-BB", [
            PolicyRule(rule_id="R2", metric="x", operator="<", threshold=5.0),
        ])
        self._register_active(v1)
        self._register_active(v2)
        self.detector.detect_all()
        self.assertTrue(self.detector.has_blocking_conflicts())

    def test_get_for_policy(self):
        v1 = _make_version("POL-TGT", [
            PolicyRule(rule_id="R1", metric="z", operator=">", threshold=1.0),
        ])
        v2 = _make_version("POL-OTHER", [
            PolicyRule(rule_id="R2", metric="z", operator="<", threshold=0.0),
        ])
        self._register_active(v1)
        self._register_active(v2)
        self.detector.detect_all()
        for_target = self.detector.get_for_policy("POL-TGT")
        self.assertGreater(len(for_target), 0)

    def test_resolve_all_for_policy(self):
        v1 = _make_version("POL-RES", [
            PolicyRule(rule_id="R1", metric="w", operator=">", threshold=50.0),
        ])
        v2 = _make_version("POL-OPP", [
            PolicyRule(rule_id="R2", metric="w", operator="<", threshold=20.0),
        ])
        self._register_active(v1)
        self._register_active(v2)
        self.detector.detect_all()
        resolved = self.detector.resolve_all_for_policy("POL-RES", "resolve", "admin")
        self.assertGreater(resolved, 0)


if __name__ == "__main__":
    unittest.main()
