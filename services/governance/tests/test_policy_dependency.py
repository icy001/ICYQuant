"""
Tests for policy_dependency.py — PolicyDependency and DependencyGraph.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.governance.policy_dependency import (
    PolicyDependency,
    DependencyType,
    DependencyGraph,
)


class TestPolicyDependency(unittest.TestCase):
    """Test dependency edge properties."""

    def test_required_dependency(self):
        dep = PolicyDependency(
            dependency_id="DEP-1",
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
            mandatory=True,
        )
        self.assertTrue(dep.is_required)
        self.assertFalse(dep.is_conflict)
        self.assertFalse(dep.is_soft)

    def test_conflict_dependency(self):
        dep = PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.CONFLICTS_WITH,
        )
        self.assertTrue(dep.is_conflict)
        self.assertFalse(dep.is_required)

    def test_soft_dependency(self):
        dep = PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REFERENCES,
        )
        self.assertTrue(dep.is_soft)

    def test_serialization(self):
        dep = PolicyDependency(
            dependency_id="DEP-1",
            source_policy_id="POL-A",
            source_version="1.0.0",
            target_policy_id="POL-B",
            target_version_constraint=">=1.0.0",
            dependency_type=DependencyType.REQUIRES,
            reason="POL-A needs POL-B",
        )
        data = dep.to_dict()
        restored = PolicyDependency.from_dict(data)
        self.assertEqual(restored.source_policy_id, "POL-A")
        self.assertEqual(restored.dependency_type, DependencyType.REQUIRES)


class TestDependencyGraph(unittest.TestCase):
    """Test DependencyGraph operations."""

    def setUp(self):
        self.graph = DependencyGraph()

    def test_add_and_query(self):
        dep = PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        )
        self.graph.add(dep)

        deps = self.graph.get_dependencies("POL-A")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].target_policy_id, "POL-B")

    def test_get_required_dependencies(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-C",
            dependency_type=DependencyType.REFERENCES,
        ))

        required = self.graph.get_required_dependencies("POL-A")
        self.assertEqual(len(required), 1)
        self.assertEqual(required[0].target_policy_id, "POL-B")

    def test_get_dependents(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))

        dependents = self.graph.get_dependents("POL-B")
        self.assertEqual(len(dependents), 1)
        self.assertEqual(dependents[0].source_policy_id, "POL-A")

    def test_validation_success(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))

        can_activate, reasons = self.graph.validate_activation(
            "POL-A", {"POL-B"}
        )
        self.assertTrue(can_activate)
        self.assertEqual(len(reasons), 0)

    def test_validation_fails_missing_requirement(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
            mandatory=True,
        ))

        can_activate, reasons = self.graph.validate_activation(
            "POL-A", {"POL-C"}
        )
        self.assertFalse(can_activate)
        self.assertGreater(len(reasons), 0)

    def test_validation_fails_conflict(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.CONFLICTS_WITH,
        ))

        can_activate, reasons = self.graph.validate_activation(
            "POL-A", {"POL-B"}
        )
        self.assertFalse(can_activate)

    def test_validation_deactivation(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))

        can_deactivate, reasons = self.graph.validate_deactivation(
            "POL-B", {"POL-A"}
        )
        self.assertFalse(can_deactivate)

    def test_cycle_detection(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))
        self.graph.add(PolicyDependency(
            source_policy_id="POL-B",
            target_policy_id="POL-C",
            dependency_type=DependencyType.REQUIRES,
        ))
        self.graph.add(PolicyDependency(
            source_policy_id="POL-C",
            target_policy_id="POL-A",
            dependency_type=DependencyType.REQUIRES,
        ))

        self.assertTrue(self.graph.has_cycle())
        cycles = self.graph.find_cycles()
        self.assertGreater(len(cycles), 0)

    def test_no_cycle(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))
        self.graph.add(PolicyDependency(
            source_policy_id="POL-B",
            target_policy_id="POL-C",
            dependency_type=DependencyType.REQUIRES,
        ))

        self.assertFalse(self.graph.has_cycle())

    def test_transitive_dependencies(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))
        self.graph.add(PolicyDependency(
            source_policy_id="POL-B",
            target_policy_id="POL-C",
            dependency_type=DependencyType.REQUIRES,
        ))

        transitive = self.graph.transitive_dependencies("POL-A")
        self.assertIn("POL-B", transitive)
        self.assertIn("POL-C", transitive)
        self.assertNotIn("POL-A", transitive)

    def test_impact_analysis(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
            reason="A needs B",
        ))

        impact = self.graph.activation_impact("POL-A")
        self.assertEqual(len(impact["required_dependencies"]), 1)

        deact_impact = self.graph.deactivation_impact("POL-B")
        self.assertGreater(deact_impact["affected_count"], 0)

    def test_remove_dependency(self):
        dep = PolicyDependency(
            dependency_id="DEP-1",
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        )
        self.graph.add(dep)
        self.assertTrue(self.graph.remove("DEP-1"))
        self.assertEqual(len(self.graph.get_dependencies("POL-A")), 0)

    def test_serialization(self):
        self.graph.add(PolicyDependency(
            source_policy_id="POL-A",
            target_policy_id="POL-B",
            dependency_type=DependencyType.REQUIRES,
        ))
        data = self.graph.to_dict()
        restored = DependencyGraph.from_dict(data)
        self.assertEqual(len(restored.dependencies), 1)


if __name__ == "__main__":
    unittest.main()
