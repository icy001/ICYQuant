"""Tests for strategy control policies and the state transition table."""

from __future__ import annotations

import pytest

from services.strategy.control.policies import (
    ACTION_TARGET_STATES,
    ALLOWED_ACTIONS_BY_STATE,
    StrategyControlPolicy,
    can_transition,
    target_state,
)


class TestStrategyControlPolicy:
    def test_all_actions_allowed_by_default(self) -> None:
        policy = StrategyControlPolicy()
        for action in ("start", "pause", "resume", "stop", "kill"):
            assert policy.allows(action)

    def test_policy_can_disable_actions(self) -> None:
        policy = StrategyControlPolicy(allow_kill=False)
        assert not policy.allows("kill")
        assert policy.allows("pause")

    def test_policy_can_disable_start(self) -> None:
        policy = StrategyControlPolicy(allow_start=False)
        assert not policy.allows("start")
        assert policy.allows("stop")

    def test_policy_is_frozen(self) -> None:
        policy = StrategyControlPolicy()
        with pytest.raises(Exception):
            policy.allow_kill = False  # type: ignore[misc]

    def test_unknown_action_returns_false(self) -> None:
        policy = StrategyControlPolicy()
        assert not policy.allows("restart")


class TestStateTransitionPolicy:
    def test_allowed_actions_by_state(self) -> None:
        assert ALLOWED_ACTIONS_BY_STATE == {
            "STOPPED": frozenset({"start", "kill"}),
            "STARTING": frozenset({"kill"}),
            "RUNNING": frozenset({"pause", "stop", "kill"}),
            "PAUSING": frozenset({"kill"}),
            "PAUSED": frozenset({"resume", "stop", "kill"}),
            "RESUMING": frozenset({"kill"}),
            "STOPPING": frozenset({"kill"}),
            "KILLED": frozenset(),
            "FAILED": frozenset({"start", "kill"}),
        }

    def test_can_transition(self) -> None:
        assert can_transition("RUNNING", "pause")
        assert can_transition("PAUSED", "resume")
        assert not can_transition("STOPPED", "pause")
        assert not can_transition("KILLED", "resume")
        assert not can_transition("ARCHIVED", "start")

    def test_action_target_states(self) -> None:
        assert ACTION_TARGET_STATES == {
            "start": "STARTING",
            "pause": "PAUSING",
            "resume": "RESUMING",
            "stop": "STOPPING",
            "kill": "KILLED",
        }

    def test_target_state_maps_accepted_action_to_intermediate_state(self) -> None:
        # Accepted/Completed separation: PAUSE is accepted as PAUSING, not PAUSED.
        assert target_state("pause") == "PAUSING"
        assert target_state("resume") == "RESUMING"
        assert target_state("stop") == "STOPPING"
        assert target_state("start") == "STARTING"
        assert target_state("kill") == "KILLED"

    def test_unknown_action_raises(self) -> None:
        with pytest.raises(KeyError):
            target_state("restart")
