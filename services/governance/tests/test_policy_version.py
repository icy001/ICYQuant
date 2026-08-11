"""
Tests for policy_version.py — PolicyVersion lifecycle, content hashing,
version cloning, serialization, and transition validation.
"""

import sys
import os
import unittest

# Ensure governance package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Bypass services/__init__.py import error by importing governance directly
import importlib.util
_spec = importlib.util.find_spec("services.governance.policy_version")
if _spec is None:
    _gov_path = os.path.join(os.path.dirname(__file__), "..")
    sys.path.insert(0, _gov_path)
    _spec = importlib.util.spec_from_file_location(
        "policy_version", os.path.join(_gov_path, "policy_version.py"),
        submodule_search_locations=[_gov_path]
    )
    policy_version = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(policy_version)
else:
    from services.governance.policy_version import (
        PolicyVersion,
    )
    policy_version_module = __import__("services.governance.policy_version", fromlist=["PolicyVersion"])
    PolicyVersion = policy_version_module.PolicyVersion

from services.governance.policy_status import PolicyLifecycleStatus, PolicyStateMachine
from services.governance.policy_priority import PolicyPriorityLevel
from services.governance.policy_rule import PolicyRule


class TestPolicyVersionLifecycle(unittest.TestCase):
    """Test the full policy version lifecycle state machine."""

    def setUp(self):
        self.version = PolicyVersion(
            policy_id="POL-TEST-01",
            name="Test Policy",
            version="1.0.0",
        )

    def test_initial_state_is_draft(self):
        self.assertEqual(self.version.status, PolicyLifecycleStatus.DRAFT)
        self.assertTrue(self.version.is_draft)
        self.assertTrue(self.version.is_editable)

    def test_full_happy_path(self):
        """DRAFT → VALIDATED → APPROVED → PUBLISHED → ACTIVE"""
        self.version.validate("tester")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.VALIDATED)
        self.assertIsNotNone(self.version.validated_at)

        self.version.approve("tester")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.APPROVED)
        self.assertIsNotNone(self.version.approved_at)

        self.version.publish("tester")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.PUBLISHED)
        self.assertIsNotNone(self.version.published_at)
        self.assertTrue(self.version.content_hash)

        self.version.activate("tester")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.ACTIVE)
        self.assertIsNotNone(self.version.activated_at)

    def test_invalid_transition_raises(self):
        """DRAFT → PUBLISHED is not allowed directly."""
        with self.assertRaises(ValueError):
            self.version.transition(PolicyLifecycleStatus.PUBLISHED)

    def test_reject_from_draft(self):
        self.version.reject("tester", "Not needed")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.REJECTED)

    def test_revoke_active(self):
        self._publish_and_activate()
        self.version.revoke("tester")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.REVOKED)

    def test_supersede(self):
        self._publish_and_activate()
        self.version.supersede("NEW-VERSION", "tester")
        self.assertEqual(self.version.status, PolicyLifecycleStatus.SUPERSEDED)
        self.assertEqual(self.version.superseded_by, "NEW-VERSION")

    def test_expire(self):
        self._publish_and_activate()
        self.version.expire()
        self.assertEqual(self.version.status, PolicyLifecycleStatus.EXPIRED)

    def test_cannot_modify_immutable(self):
        self._publish_and_activate()
        self.assertTrue(self.version.is_immutable)

    def test_available_transitions(self):
        transitions = self.version.available_transitions
        self.assertIn(PolicyLifecycleStatus.VALIDATED, transitions)
        self.assertIn(PolicyLifecycleStatus.REJECTED, transitions)
        self.assertNotIn(PolicyLifecycleStatus.ACTIVE, transitions)

    def _publish_and_activate(self):
        self.version.validate("tester")
        self.version.approve("tester")
        self.version.publish("tester")
        self.version.activate("tester")


class TestPolicyVersionContentHash(unittest.TestCase):
    """Test content hashing for integrity verification."""

    def setUp(self):
        self.version = PolicyVersion(
            policy_id="POL-HASH-01",
            name="Hash Test Policy",
            version="1.0.0",
        )
        self.version.add_rule(PolicyRule(
            rule_id="R1", metric="test_metric", operator=">=", threshold=10.0,
        ))

    def test_hash_computed_on_publish(self):
        self.version.validate("tester")
        self.version.approve("tester")
        self.version.publish("tester")
        self.assertTrue(self.version.content_hash)
        self.assertEqual(len(self.version.content_hash), 64)  # SHA-256

    def test_hash_changes_on_rule_change(self):
        self.version.validate("tester")
        self.version.approve("tester")
        self.version.publish("tester")
        original_hash = self.version.content_hash

        # Create new draft from published version
        draft = self.version.create_next_draft("patch")
        self.assertNotEqual(draft.content_hash, original_hash)

    def test_verify_checksum(self):
        self.version.validate("tester")
        self.version.approve("tester")
        self.version.publish("tester")
        self.assertTrue(self.version.verify_checksum())

    def test_checksum_detects_tampering(self):
        self.version.validate("tester")
        self.version.approve("tester")
        self.version.publish("tester")
        # Tamper with content
        self.version.name = "Tampered Name"
        self.assertFalse(self.version.verify_checksum())


class TestPolicyVersionClone(unittest.TestCase):
    """Test version cloning and next-draft creation."""

    def setUp(self):
        self.version = PolicyVersion(
            policy_id="POL-CLONE-01",
            name="Original Policy",
            version="1.0.0",
            description="Original description",
        )
        self.version.add_rule(PolicyRule(
            rule_id="R1", metric="m1", operator=">", threshold=5.0,
        ))

    def test_create_next_draft_minor_bump(self):
        draft = self.version.create_next_draft("minor")
        self.assertEqual(draft.version, "1.1.0")
        self.assertEqual(draft.status, PolicyLifecycleStatus.DRAFT)
        self.assertEqual(draft.parent_version, self.version.version_id)
        self.assertEqual(draft.policy_id, self.version.policy_id)
        self.assertEqual(len(draft.rules), len(self.version.rules))

    def test_create_next_draft_major_bump(self):
        draft = self.version.create_next_draft("major")
        self.assertEqual(draft.version, "2.0.0")

    def test_create_next_draft_patch_bump(self):
        draft = self.version.create_next_draft("patch")
        self.assertEqual(draft.version, "1.0.1")

    def test_rules_are_deep_copied(self):
        """Rule modification in clone should not affect original."""
        draft = self.version.create_next_draft("minor")
        draft.add_rule(PolicyRule(rule_id="R2", metric="m2"))
        self.assertEqual(len(self.version.rules), 1)
        self.assertEqual(len(draft.rules), 2)


class TestPolicyVersionSerialization(unittest.TestCase):
    """Test to_dict / from_dict round-trip."""

    def setUp(self):
        self.version = PolicyVersion(
            policy_id="POL-SER-01",
            name="Serialization Test",
            version="2.3.1",
            description="Test serialization",
        )
        self.version.add_rule(PolicyRule(
            rule_id="R1", metric="m1", operator=">=", threshold=10.0,
        ))
        self.version.validate("tester")
        self.version.approve("tester")
        self.version.publish("tester")

    def test_round_trip(self):
        data = self.version.to_dict()
        restored = PolicyVersion.from_dict(data)
        self.assertEqual(restored.policy_id, self.version.policy_id)
        self.assertEqual(restored.version, self.version.version)
        self.assertEqual(restored.status, self.version.status)
        self.assertEqual(restored.content_hash, self.version.content_hash)
        self.assertEqual(len(restored.rules), len(self.version.rules))

    def test_display_version(self):
        self.assertEqual(self.version.display_version, "v2.3.1")

    def test_full_identifier(self):
        self.assertEqual(self.version.full_identifier, "POL-SER-01@2.3.1")


class TestPolicyVersionHelpers(unittest.TestCase):
    """Test helper properties and methods."""

    def test_age_seconds(self):
        import time
        v = PolicyVersion()
        time.sleep(0.01)
        self.assertGreater(v.age_seconds, 0)

    def test_can_transition_to(self):
        v = PolicyVersion()
        self.assertTrue(v.can_transition_to(PolicyLifecycleStatus.VALIDATED))
        self.assertFalse(v.can_transition_to(PolicyLifecycleStatus.ACTIVE))

    def test_priority_property(self):
        v = PolicyVersion(priority=PolicyPriorityLevel.CRITICAL)
        self.assertEqual(v.priority, PolicyPriorityLevel.CRITICAL)
        self.assertTrue(v.priority.is_blocking)


if __name__ == "__main__":
    unittest.main()
