"""
Tests for policy_effect.py — PolicyEffect types, severity, aggregation,
and factory methods.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.governance.policy_effect import (
    PolicyEffect,
    EffectType,
    EffectSeverity,
    AggregatedEffects,
)


class TestEffectType(unittest.TestCase):
    """Test EffectType classification."""

    def test_blocking_types(self):
        self.assertTrue(EffectType.BLOCK.is_blocking)
        self.assertTrue(EffectType.SUSPEND.is_blocking)
        self.assertTrue(EffectType.EMERGENCY_EXIT.is_blocking)
        self.assertFalse(EffectType.WARNING.is_blocking)
        self.assertFalse(EffectType.INFO.is_blocking)

    def test_review_types(self):
        self.assertTrue(EffectType.FLAG.requires_review)
        self.assertTrue(EffectType.REQUIRE_APPROVAL.requires_review)
        self.assertFalse(EffectType.BLOCK.requires_review)

    def test_advisory_types(self):
        self.assertTrue(EffectType.INFO.is_advisory)
        self.assertTrue(EffectType.WARNING.is_advisory)
        self.assertFalse(EffectType.BLOCK.is_advisory)

    def test_permissive_types(self):
        self.assertTrue(EffectType.ALLOW.is_permissive)
        self.assertTrue(EffectType.NOTIFY.is_permissive)


class TestEffectSeverity(unittest.TestCase):
    """Test severity mapping and ordering."""

    def test_severity_for_effect_type(self):
        self.assertEqual(
            EffectSeverity.for_effect_type(EffectType.BLOCK),
            EffectSeverity.BLOCKING
        )
        self.assertEqual(
            EffectSeverity.for_effect_type(EffectType.EMERGENCY_EXIT),
            EffectSeverity.BLOCKING
        )
        self.assertEqual(
            EffectSeverity.for_effect_type(EffectType.WARNING),
            EffectSeverity.MEDIUM
        )
        self.assertEqual(
            EffectSeverity.for_effect_type(EffectType.ALLOW),
            EffectSeverity.NONE
        )

    def test_severity_values(self):
        self.assertEqual(EffectSeverity.NONE.value, 0)
        self.assertEqual(EffectSeverity.BLOCKING.value, 100)
        self.assertGreater(EffectSeverity.CRITICAL.value, EffectSeverity.HIGH.value)


class TestPolicyEffect(unittest.TestCase):
    """Test PolicyEffect creation and properties."""

    def test_allow_factory(self):
        effect = PolicyEffect.allow(
            source_policy_id="POL-1",
            reason="All clear",
        )
        self.assertEqual(effect.effect_type, EffectType.ALLOW)
        self.assertFalse(effect.is_blocking)

    def test_warn_factory(self):
        effect = PolicyEffect.warn(
            source_policy_id="POL-1",
            source_rule_id="R1",
            metric="leverage",
            actual=3.5,
            expected="<= 3.0",
            message="Leverage warning",
        )
        self.assertEqual(effect.effect_type, EffectType.WARNING)
        self.assertTrue(effect.is_advisory)
        self.assertEqual(effect.metric, "leverage")
        self.assertEqual(effect.actual_value, 3.5)

    def test_block_factory(self):
        effect = PolicyEffect.block(
            source_policy_id="POL-1",
            source_rule_id="R1",
            metric="concentration",
            actual=0.45,
            expected="<= 0.30",
            reason="Concentration limit exceeded",
        )
        self.assertEqual(effect.effect_type, EffectType.BLOCK)
        self.assertTrue(effect.is_blocking)
        self.assertEqual(effect.severity, EffectSeverity.BLOCKING)

    def test_require_approval_factory(self):
        effect = PolicyEffect.require_approval(
            source_policy_id="POL-1",
            reason="Large allocation",
        )
        self.assertTrue(effect.requires_review)
        self.assertEqual(effect.severity, EffectSeverity.HIGH)

    def test_emergency_exit_factory(self):
        effect = PolicyEffect.emergency_exit(
            source_policy_id="POL-1",
            reason="Market circuit breaker triggered",
        )
        self.assertEqual(effect.effect_type, EffectType.EMERGENCY_EXIT)
        self.assertTrue(effect.is_blocking)
        self.assertEqual(effect.severity, EffectSeverity.BLOCKING)

    def test_display_string(self):
        effect = PolicyEffect.warn(
            source_policy_id="POL-1",
            metric="leverage",
            actual=3.5,
            message="Leverage high",
        )
        self.assertIn("WARNING", effect.display_string)
        self.assertIn("Leverage high", effect.display_string)

    def test_post_init_sets_severity(self):
        """Severity should be auto-set from effect_type if not explicitly set."""
        effect = PolicyEffect(effect_type=EffectType.BLOCK)
        self.assertEqual(effect.severity, EffectSeverity.BLOCKING)


class TestAggregatedEffects(unittest.TestCase):
    """Test effect aggregation logic."""

    def test_aggregate_all_allow(self):
        effects = [
            PolicyEffect.allow(source_policy_id="P1"),
            PolicyEffect(effect_type=EffectType.INFO),
        ]
        agg = AggregatedEffects.aggregate(effects)
        self.assertEqual(agg.overall_outcome, "ALLOW")

    def test_aggregate_with_warnings(self):
        effects = [
            PolicyEffect.warn(source_policy_id="P1", metric="m1"),
            PolicyEffect(effect_type=EffectType.INFO),
        ]
        agg = AggregatedEffects.aggregate(effects)
        self.assertEqual(agg.overall_outcome, "ALLOW")

    def test_aggregate_with_review(self):
        effects = [
            PolicyEffect.require_approval(source_policy_id="P1"),
            PolicyEffect.warn(source_policy_id="P2", metric="m1"),
        ]
        agg = AggregatedEffects.aggregate(effects)
        self.assertEqual(agg.overall_outcome, "REVIEW")
        self.assertTrue(agg.requires_review)

    def test_aggregate_blocking(self):
        effects = [
            PolicyEffect.block(source_policy_id="P1", metric="m1"),
            PolicyEffect.warn(source_policy_id="P2", metric="m2"),
        ]
        agg = AggregatedEffects.aggregate(effects)
        self.assertEqual(agg.overall_outcome, "BLOCK")
        self.assertTrue(agg.is_blocking)

    def test_highest_severity(self):
        effects = [
            PolicyEffect.allow(source_policy_id="P1"),
            PolicyEffect.warn(source_policy_id="P2", metric="m2"),
            PolicyEffect.block(source_policy_id="P3", metric="m3"),
        ]
        agg = AggregatedEffects.aggregate(effects)
        self.assertEqual(agg.highest_severity, EffectSeverity.BLOCKING)

    def test_empty_effects(self):
        agg = AggregatedEffects.aggregate([])
        self.assertEqual(agg.overall_outcome, "ALLOW")
        self.assertEqual(agg.highest_severity, EffectSeverity.NONE)


class TestPolicyEffectSerialization(unittest.TestCase):
    """Test effect serialization."""

    def test_round_trip(self):
        effect = PolicyEffect.block(
            source_policy_id="POL-1",
            source_version_id="PV-123",
            source_rule_id="R1",
            metric="leverage",
            actual=5.0,
            expected="<= 3.0",
            reason="Too high",
        )
        data = effect.to_dict()
        restored = PolicyEffect.from_dict(data)
        self.assertEqual(restored.effect_type, effect.effect_type)
        self.assertEqual(restored.severity, effect.severity)
        self.assertEqual(restored.metric, effect.metric)
        self.assertEqual(restored.actual_value, 5.0)


if __name__ == "__main__":
    unittest.main()
