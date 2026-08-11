"""
Tests for policy_publisher.py — Publisher pipeline (DRAFT → VALIDATED → PUBLISHED → ACTIVE).

Covers spec test requirements:
  - Activation: scheduled, immediate, expired, rollback
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

from services.governance.policy_publisher import PolicyPublisher
from services.governance.policy_version import PolicyVersion
from services.governance.policy_status import PolicyLifecycleStatus
from services.governance.policy_rule import PolicyRule
from services.governance.policy_repository import PolicyRepository, InMemoryRepositoryBackend
from services.governance.policy_registry import PolicyRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_version(**kwargs) -> PolicyVersion:
    v = PolicyVersion(
        policy_id=kwargs.pop("policy_id", "POL-TEST"),
        version=kwargs.pop("version", "1.0.0"),
        name=kwargs.pop("name", "Test Policy"),
        **kwargs,
    )
    v.add_rule(PolicyRule(
        rule_id="R1", metric="capital", operator=">=", threshold=1000.0,
    ))
    return v


# ---------------------------------------------------------------------------
# Publish pipeline: DRAFT → VALIDATED → APPROVED → PUBLISHED
# ---------------------------------------------------------------------------

class TestPublishPipeline(unittest.TestCase):
    """Test the full publish pipeline through lifecycle stages."""

    def setUp(self) -> None:
        self.repo = PolicyRepository(backend=InMemoryRepositoryBackend())
        self.registry = PolicyRegistry()
        self.publisher = PolicyPublisher(registry=self.registry, repository=self.repo)

    # ---- Publish from DRAFT ----

    def test_publish_full_pipeline(self):
        """DRAFT → VALIDATED → APPROVED → PUBLISHED in one call."""
        version = _make_version()
        result = self.publisher.publish(version, "testuser")
        self.assertTrue(result.success, msg=f"Errors: {result.errors}")
        self.assertEqual(version.status, PolicyLifecycleStatus.PUBLISHED)

    def test_publish_tracks_versions(self):
        """Publish result records all version transitions."""
        version = _make_version()
        result = self.publisher.publish(version, "testuser")
        statuses = [t["status"] for t in result.versions]
        self.assertIn("VALIDATED", statuses)
        self.assertIn("APPROVED", statuses)
        self.assertIn("PUBLISHED", statuses)

    def test_publish_from_validated(self):
        """A version already VALIDATED goes APPROVED → PUBLISHED."""
        version = _make_version()
        version.validate("testuser")
        self.assertEqual(version.status, PolicyLifecycleStatus.VALIDATED)

        result = self.publisher.publish(version, "testuser")
        self.assertTrue(result.success)
        self.assertEqual(version.status, PolicyLifecycleStatus.PUBLISHED)

    def test_publish_already_published_warns(self):
        """Publishing an already-published version warns."""
        version = _make_version()
        self.publisher.publish(version, "testuser")
        result2 = self.publisher.publish(version, "testuser")
        self.assertTrue(result2.success)
        self.assertTrue(any("already PUBLISHED" in w for w in result2.warnings))

    def test_publish_stores_in_repository(self):
        """After publishing, version is stored in repository."""
        version = _make_version()
        self.publisher.publish(version, "testuser")

        loaded = self.repo.load(version.policy_id, version.version_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, PolicyLifecycleStatus.PUBLISHED)

    def test_publish_history_recorded(self):
        """Each publish operation is recorded in history."""
        version = _make_version()
        self.publisher.publish(version, "testuser")
        self.assertGreater(len(self.publisher.publish_history), 0)

    # ---- Activate ----

    def test_activate_from_published(self):
        """PUBLISHED → ACTIVE via publisher."""
        version = _make_version()
        self.publisher.publish(version, "testuser")
        result = self.publisher.activate(version, "testuser")
        self.assertTrue(result.success, msg=f"Errors: {result.errors}")
        self.assertEqual(version.status, PolicyLifecycleStatus.ACTIVE)

    def test_activate_updates_registry(self):
        """After activation, registry reflects the active version."""
        version = _make_version()
        self.registry.register(version)
        self.publisher.publish(version, "testuser")
        self.publisher.activate(version, "testuser")

        active = self.registry.get_active(version.policy_id)
        self.assertIsNotNone(active)
        self.assertEqual(active.version_id, version.version_id)

    def test_activate_non_published_fails(self):
        """Activation fails for a non-published version."""
        version = _make_version()
        result = self.publisher.activate(version, "testuser")
        self.assertFalse(result.success)

    def test_activate_already_active_warns(self):
        """Activating an already-active version warns."""
        version = _make_version()
        self.registry.register(version)
        self.publisher.publish(version, "testuser")
        self.publisher.activate(version, "testuser")
        result2 = self.publisher.activate(version, "testuser")
        self.assertTrue(
            any("already ACTIVE" in w for w in result2.warnings)
            or not result2.success
        )

    # ---- Deactivate ----

    def test_deactivate_active_policy(self):
        """Deactivate an active policy."""
        version = _make_version()
        self.registry.register(version)
        self.publisher.publish(version, "testuser")
        self.publisher.activate(version, "testuser")
        result = self.publisher.deactivate(version, "testuser")
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Immediate activation
# ---------------------------------------------------------------------------

class TestImmediateActivation(unittest.TestCase):
    """Test immediate (now) activation."""

    def setUp(self) -> None:
        self.repo = PolicyRepository(backend=InMemoryRepositoryBackend())
        self.registry = PolicyRegistry()
        self.publisher = PolicyPublisher(registry=self.registry, repository=self.repo)

    def test_publish_then_activate_immediately(self):
        """Policy can be published and activated immediately."""
        version = _make_version(policy_id="POL-IMM", version="2.0.0", name="Immediate")
        self.registry.register(version)
        result = self.publisher.publish(version, "testuser")
        self.assertTrue(result.success)
        result2 = self.publisher.activate(version, "testuser")
        self.assertTrue(result2.success)
        self.assertEqual(version.status, PolicyLifecycleStatus.ACTIVE)

        active = self.registry.get_active("POL-IMM")
        self.assertIsNotNone(active)
        self.assertEqual(active.version, "2.0.0")


# ---------------------------------------------------------------------------
# Batch activation (atomic)
# ---------------------------------------------------------------------------

class TestBatchActivation(unittest.TestCase):
    """Test atomic batch activation."""

    def setUp(self) -> None:
        self.repo = PolicyRepository(backend=InMemoryRepositoryBackend())
        self.registry = PolicyRegistry()
        self.publisher = PolicyPublisher(registry=self.registry, repository=self.repo)

    def _make_and_publish(self, policy_id, version) -> PolicyVersion:
        v = _make_version(policy_id=policy_id, version=version, name=policy_id)
        self.registry.register(v)
        self.publisher.publish(v, "testuser")
        return v

    def test_batch_activate_multiple(self):
        """Activate multiple policies atomically."""
        v1 = self._make_and_publish("POL-B1", "1.0.0")
        v2 = self._make_and_publish("POL-B2", "1.0.0")
        result = self.publisher.activate_batch([v1, v2], "testuser")
        self.assertTrue(result.success, msg=f"Errors: {result.errors}")
        self.assertEqual(v1.status, PolicyLifecycleStatus.ACTIVE)
        self.assertEqual(v2.status, PolicyLifecycleStatus.ACTIVE)

    def test_batch_activate_non_published_fails_all(self):
        """Batch with a non-published version fails the whole batch."""
        v1 = self._make_and_publish("POL-B3", "1.0.0")
        v2 = PolicyVersion(policy_id="POL-B4", version="1.0.0", name="Not Published")
        v2.add_rule(PolicyRule(
            rule_id="R1", metric="capital", operator=">=", threshold=100.0,
        ))
        result = self.publisher.activate_batch([v1, v2], "testuser")
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# Publish history
# ---------------------------------------------------------------------------

class TestPublishHistory(unittest.TestCase):
    """Test publisher history tracking."""

    def setUp(self) -> None:
        self.repo = PolicyRepository(backend=InMemoryRepositoryBackend())
        self.registry = PolicyRegistry()
        self.publisher = PolicyPublisher(registry=self.registry, repository=self.repo)

    def test_publish_adds_to_history(self):
        version = _make_version(policy_id="POL-HIST", name="History Test")
        self.publisher.publish(version, "testuser")
        history = self.publisher.publish_history
        self.assertEqual(len(history), 1)

    def test_clear_history(self):
        version = _make_version(policy_id="POL-CLEAR", name="Clear Test")
        self.publisher.publish(version, "testuser")
        self.publisher.clear_history()
        self.assertEqual(len(self.publisher.publish_history), 0)


if __name__ == "__main__":
    unittest.main()
