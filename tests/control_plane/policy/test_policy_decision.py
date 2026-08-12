"""Unit tests: PolicyDecision and fail-safe ordering."""

from __future__ import annotations

from services.control_plane.policy.policy_decision import (
    FAIL_SAFE_RANK,
    PolicyDecision,
    is_at_least,
    is_more_severe,
    most_severe,
    sorted_by_severity,
)


class TestPolicyDecision:
    def test_enum_members(self):
        assert {d.value for d in PolicyDecision} == {
            "ALLOW",
            "DEGRADE",
            "RECOVER",
            "BLOCK",
            "HALT",
            "ESCALATE",
        }

    def test_fail_safe_ordering(self):
        assert FAIL_SAFE_RANK[PolicyDecision.ALLOW] < FAIL_SAFE_RANK[PolicyDecision.DEGRADE]
        assert FAIL_SAFE_RANK[PolicyDecision.DEGRADE] < FAIL_SAFE_RANK[PolicyDecision.BLOCK]
        assert FAIL_SAFE_RANK[PolicyDecision.BLOCK] < FAIL_SAFE_RANK[PolicyDecision.HALT]

    def test_most_severe_wins(self):
        decisions = [
            PolicyDecision.ALLOW,
            PolicyDecision.DEGRADE,
            PolicyDecision.HALT,
        ]
        assert most_severe(decisions) is PolicyDecision.HALT

    def test_most_severe_block_beats_degrade(self):
        decisions = [PolicyDecision.DEGRADE, PolicyDecision.BLOCK]
        assert most_severe(decisions) is PolicyDecision.BLOCK

    def test_most_severe_same_decision(self):
        decisions = [PolicyDecision.BLOCK, PolicyDecision.BLOCK]
        assert most_severe(decisions) is PolicyDecision.BLOCK

    def test_most_severe_empty_is_allow(self):
        assert most_severe([]) is PolicyDecision.ALLOW

    def test_is_at_least(self):
        assert is_at_least(PolicyDecision.HALT, PolicyDecision.BLOCK)
        assert not is_at_least(PolicyDecision.DEGRADE, PolicyDecision.BLOCK)

    def test_is_more_severe(self):
        assert is_more_severe(PolicyDecision.HALT, PolicyDecision.DEGRADE)
        assert not is_more_severe(PolicyDecision.BLOCK, PolicyDecision.BLOCK)

    def test_sorted_by_severity(self):
        assert sorted_by_severity(
            [PolicyDecision.DEGRADE, PolicyDecision.ALLOW, PolicyDecision.HALT]
        ) == [PolicyDecision.HALT, PolicyDecision.DEGRADE, PolicyDecision.ALLOW]
