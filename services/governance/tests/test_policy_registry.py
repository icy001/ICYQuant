"""
Tests for policy_registry.py — PolicyRegistry registration, lookup,
activation management, and scope/priority-based queries.

Also exercises policy_repository.py in-memory persistence.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.governance.policy_version import PolicyVersion
from services.governance.policy_registry import PolicyRegistry
from services.governance.policy_repository import (
    PolicyRepository,
    InMemoryRepositoryBackend,
)
from services.governance.policy_status import PolicyLifecycleStatus
from services.governance.policy_priority import PolicyPriorityLevel
from services.governance.policy_rule import PolicyRule


class TestPolicyRegistry(unittest.TestCase):
    """Test PolicyRegistry operations."""

    def setUp(self):
        self.registry = PolicyRegistry()

    def _make_version(self, policy_id, name, version="1.0.0", scope="GLOBAL",
                      priority=PolicyPriorityLevel.NORMAL):
        pv = PolicyVersion(
            policy_id=policy_id,
            name=name,
            version=version,
            scope=scope,
            priority=priority,
        )
        pv.add_rule(PolicyRule(
            rule_id=f"R-{policy_id}",
            metric="test_metric",
            operator=">=",
            threshold=0.0,
        ))
        return pv

    def test_register_and_get(self):
        pv = self._make_version("POL-1", "Policy One")
        self.registry.register(pv)

        found = self.registry.get("POL-1")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Policy One")

    def test_get_nonexistent(self):
        self.assertIsNone(self.registry.get("NONEXISTENT"))

    def test_multiple_versions(self):
        pv1 = self._make_version("POL-1", "Policy One", version="1.0.0")
        pv2 = self._make_version("POL-1", "Policy One v2", version="2.0.0")
        self.registry.register(pv1)
        self.registry.register(pv2)

        versions = self.registry.get_all_versions("POL-1")
        self.assertEqual(len(versions), 2)

    def test_set_active(self):
        pv = self._make_version("POL-1", "Policy One")
        pv.validate("tester")
        pv.approve("tester")
        pv.publish("tester")
        self.registry.register(pv)

        self.registry.set_active("POL-1", pv.version_id)
        active = self.registry.get_active("POL-1")
        self.assertIsNotNone(active)
        self.assertEqual(active.status, PolicyLifecycleStatus.ACTIVE)

    def test_deactivate(self):
        pv = self._make_version("POL-1", "Policy One")
        pv.validate("tester")
        pv.approve("tester")
        pv.publish("tester")
        self.registry.register(pv)
        self.registry.set_active("POL-1", pv.version_id)

        self.registry.deactivate("POL-1")
        self.assertIsNone(self.registry.get_active("POL-1"))

    def test_policy_count(self):
        self.registry.register(self._make_version("POL-1", "P1"))
        self.registry.register(self._make_version("POL-2", "P2"))
        self.registry.register(self._make_version("POL-2", "P2", version="2.0.0"))
        self.assertEqual(self.registry.policy_count, 2)
        self.assertEqual(self.registry.version_count, 3)

    def test_list_by_scope(self):
        self.registry.register(self._make_version(
            "POL-1", "Global Policy", scope="GLOBAL"
        ))
        pv = self._make_version("POL-2", "Portfolio Policy", scope="PORTFOLIO")
        pv.validate("tester")
        pv.approve("tester")
        pv.publish("tester")
        self.registry.register(pv)
        self.registry.set_active("POL-2", pv.version_id)

        portfolio_policies = self.registry.list_by_scope("PORTFOLIO")
        # At least the portfolio-specific one
        self.assertGreaterEqual(len(portfolio_policies), 1)

    def test_list_for_evaluation(self):
        """Test priority-sorted evaluation listing."""
        pv_low = self._make_version(
            "POL-LOW", "Low Priority", priority=PolicyPriorityLevel.LOW
        )
        pv_crit = self._make_version(
            "POL-CRIT", "Critical", priority=PolicyPriorityLevel.CRITICAL
        )
        pv_low.validate("tester"); pv_low.approve("tester"); pv_low.publish("tester")
        pv_crit.validate("tester"); pv_crit.approve("tester"); pv_crit.publish("tester")
        self.registry.register(pv_low)
        self.registry.register(pv_crit)
        self.registry.set_active("POL-LOW", pv_low.version_id)
        self.registry.set_active("POL-CRIT", pv_crit.version_id)

        ordered = self.registry.list_for_evaluation()
        # Critical should come before Low
        self.assertEqual(ordered[0].policy_id, "POL-CRIT")
        self.assertEqual(ordered[1].policy_id, "POL-LOW")

    def test_find_by_name(self):
        self.registry.register(self._make_version("POL-1", "Risk Limits"))
        self.registry.register(self._make_version("POL-2", "Capital Requirements"))
        found = self.registry.find_by_name("risk")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "Risk Limits")

    def test_unregister(self):
        self.registry.register(self._make_version("POL-1", "P1"))
        self.assertTrue(self.registry.unregister("POL-1", self.registry.get("POL-1").version_id))
        self.assertIsNone(self.registry.get("POL-1"))

    def test_serialization(self):
        self.registry.register(self._make_version("POL-1", "P1"))
        self.registry.register(self._make_version("POL-2", "P2"))
        data = self.registry.to_dict()
        restored = PolicyRegistry.from_dict(data)
        self.assertEqual(restored.policy_count, 2)


class TestPolicyRepository(unittest.TestCase):
    """Test PolicyRepository with in-memory backend."""

    def setUp(self):
        self.backend = InMemoryRepositoryBackend()
        self.repo = PolicyRepository(backend=self.backend)

    def _make_version(self, policy_id, name, version="1.0.0"):
        pv = PolicyVersion(
            policy_id=policy_id,
            name=name,
            version=version,
        )
        pv.add_rule(PolicyRule(rule_id=f"R-{policy_id}", metric="m"))
        return pv

    def test_save_and_load(self):
        pv = self._make_version("POL-1", "Test Policy")
        self.repo.save(pv)
        loaded = self.repo.load("POL-1", pv.version_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Test Policy")

    def test_load_all(self):
        self.repo.save(self._make_version("POL-1", "P1", "1.0.0"))
        self.repo.save(self._make_version("POL-1", "P1 v2", "2.0.0"))
        all_versions = self.repo.load_all("POL-1")
        self.assertEqual(len(all_versions), 2)

    def test_delete(self):
        pv = self._make_version("POL-1", "P1")
        self.repo.save(pv)
        self.assertTrue(self.repo.delete("POL-1", pv.version_id))
        self.assertIsNone(self.repo.load("POL-1", pv.version_id))

    def test_snapshot_and_restore(self):
        pv = self._make_version("POL-1", "Original")
        self.repo.save(pv)
        snapshot_id = self.repo.create_snapshot("test-snap")
        self.repo.clear()
        self.assertEqual(len(self.repo.list_policy_ids()), 0)
        count = self.repo.restore_snapshot("test-snap")
        self.assertGreater(count, 0)
        self.assertIn("POL-1", self.repo.list_policy_ids())

    def test_audit_trail(self):
        pv = self._make_version("POL-1", "P1")
        self.repo.save(pv, "test_actor")
        trail = self.repo.get_audit_trail("POL-1")
        self.assertGreater(len(trail), 0)
        self.assertEqual(trail[-1].operation, "SAVE")
        self.assertEqual(trail[-1].actor, "test_actor")

    def test_export_import(self):
        self.repo.save(self._make_version("POL-1", "P1"))
        self.repo.save(self._make_version("POL-2", "P2"))
        exported = self.repo.export_all()
        self.repo.clear()
        self.repo.import_all(exported)
        self.assertEqual(len(self.repo.list_policy_ids()), 2)

    def test_exists(self):
        pv = self._make_version("POL-1", "P1")
        self.repo.save(pv)
        self.assertTrue(self.repo.exists("POL-1", pv.version_id))
        self.assertFalse(self.repo.exists("POL-1", "NONEXISTENT"))


class TestPolicyRegistryIntegration(unittest.TestCase):
    """Integration test: registry + repository."""

    def test_registry_with_repository(self):
        repo_backend = InMemoryRepositoryBackend()
        repo = PolicyRepository(backend=repo_backend)
        registry = PolicyRegistry()

        pv = PolicyVersion(
            policy_id="POL-INT-01",
            name="Integrated Policy",
            version="1.0.0",
        )
        pv.add_rule(PolicyRule(rule_id="R1", metric="m1"))
        pv.validate("tester")
        pv.approve("tester")
        pv.publish("tester")

        # Save to repo and register
        repo.save(pv)
        registry.register(pv)
        registry.set_active("POL-INT-01", pv.version_id)

        # Verify round-trip
        loaded = repo.load("POL-INT-01", pv.version_id)
        self.assertIsNotNone(loaded)
        active = registry.get_active("POL-INT-01")
        self.assertIsNotNone(active)
        self.assertEqual(loaded.version_id, active.version_id)


if __name__ == "__main__":
    unittest.main()
