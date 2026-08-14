"""Tests for the strategy transition value object."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.strategy.control.transition import StrategyTransition


class TestStrategyTransition:
    def test_transition_carries_expected_fields(self) -> None:
        transition = StrategyTransition(
            strategy_id="STRAT-001",
            command_id="CMD-001",
            from_state="RUNNING",
            to_state="PAUSING",
            action="pause",
        )

        assert transition.strategy_id == "STRAT-001"
        assert transition.command_id == "CMD-001"
        assert transition.from_state == "RUNNING"
        assert transition.to_state == "PAUSING"
        assert transition.action == "pause"

    def test_transition_is_immutable(self) -> None:
        transition = StrategyTransition(
            strategy_id="STRAT-001",
            command_id="CMD-001",
            from_state="RUNNING",
            to_state="PAUSING",
            action="pause",
        )
        with pytest.raises(FrozenInstanceError):
            transition.action = "stop"  # type: ignore[misc]

    def test_transition_only_describes_it_never_executes(self) -> None:
        # The transition value object has no side effects and no runtime
        # coupling; it is pure data describing a state change.
        transition = StrategyTransition(
            strategy_id="STRAT-001",
            command_id="CMD-001",
            from_state="STOPPED",
            to_state="STARTING",
            action="start",
        )
        assert transition.to_state == "STARTING"
