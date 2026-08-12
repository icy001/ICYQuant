"""Unit tests: PolicyPriority ranks and helpers."""

from __future__ import annotations

from services.control_plane.policy.policy_priority import (
    PolicyPriority,
    highest_priority,
    lowest_priority,
    priority_ge,
    sorted_priorities,
)


class TestPolicyPriority:
    def test_enum_members(self):
        assert {p.value for p in PolicyPriority} == {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }

    def test_rank_ordering(self):
        assert PolicyPriority.LOW.rank < PolicyPriority.MEDIUM.rank
        assert PolicyPriority.MEDIUM.rank < PolicyPriority.HIGH.rank
        assert PolicyPriority.HIGH.rank < PolicyPriority.CRITICAL.rank

    def test_priority_ge(self):
        assert priority_ge(PolicyPriority.CRITICAL, PolicyPriority.LOW)
        assert priority_ge(PolicyPriority.HIGH, PolicyPriority.HIGH)
        assert not priority_ge(PolicyPriority.LOW, PolicyPriority.HIGH)

    def test_highest_priority(self):
        assert (
            highest_priority(
                [PolicyPriority.LOW, PolicyPriority.HIGH, PolicyPriority.MEDIUM]
            )
            is PolicyPriority.HIGH
        )

    def test_highest_priority_empty_is_low(self):
        assert highest_priority([]) is PolicyPriority.LOW

    def test_lowest_priority(self):
        assert (
            lowest_priority(
                [PolicyPriority.CRITICAL, PolicyPriority.MEDIUM]
            )
            is PolicyPriority.MEDIUM
        )

    def test_sorted_priorities_most_severe_first(self):
        assert sorted_priorities(
            [PolicyPriority.LOW, PolicyPriority.CRITICAL, PolicyPriority.MEDIUM]
        ) == [PolicyPriority.CRITICAL, PolicyPriority.MEDIUM, PolicyPriority.LOW]
