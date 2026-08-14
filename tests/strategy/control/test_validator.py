"""Tests for the strategy control state transition validator."""

from __future__ import annotations

import pytest

from services.strategy.control.validator import StrategyControlValidator
from services.strategy.domain.control_state import StrategyControlState


@pytest.fixture()
def validator() -> StrategyControlValidator:
    return StrategyControlValidator()


class TestLegalTransitions:
    def test_running_can_pause(self, validator: StrategyControlValidator) -> None:
        validator.validate("RUNNING", "pause")

    def test_running_can_stop(self, validator: StrategyControlValidator) -> None:
        validator.validate("RUNNING", "stop")

    def test_running_can_kill(self, validator: StrategyControlValidator) -> None:
        validator.validate("RUNNING", "kill")

    def test_paused_can_resume(self, validator: StrategyControlValidator) -> None:
        validator.validate("PAUSED", "resume")

    def test_paused_can_stop(self, validator: StrategyControlValidator) -> None:
        validator.validate("PAUSED", "stop")

    def test_stopped_can_start(self, validator: StrategyControlValidator) -> None:
        validator.validate("STOPPED", "start")

    def test_failed_can_start(self, validator: StrategyControlValidator) -> None:
        validator.validate("FAILED", "start")

    def test_failed_can_kill(self, validator: StrategyControlValidator) -> None:
        validator.validate("FAILED", "kill")

    def test_transitional_states_only_accept_kill(
        self, validator: StrategyControlValidator
    ) -> None:
        for state in ("STARTING", "PAUSING", "RESUMING", "STOPPING"):
            validator.validate(state, "kill")

    def test_enum_state_equivalent_to_string(
        self, validator: StrategyControlValidator
    ) -> None:
        validator.validate(StrategyControlState.RUNNING, "pause")


class TestIllegalTransitions:
    def test_pause_from_stopped_is_rejected(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError):
            validator.validate("STOPPED", "pause")

    def test_killed_strategy_cannot_resume(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError):
            validator.validate("KILLED", "resume")

    def test_killed_strategy_cannot_do_anything(
        self, validator: StrategyControlValidator
    ) -> None:
        for action in ("start", "pause", "resume", "stop", "kill"):
            with pytest.raises(ValueError):
                validator.validate("KILLED", action)

    def test_start_from_running_is_rejected(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError):
            validator.validate("RUNNING", "start")

    def test_resume_from_running_is_rejected(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError):
            validator.validate("RUNNING", "resume")

    def test_start_from_transitional_state_is_rejected(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError):
            validator.validate("STARTING", "pause")

    def test_stop_from_stopped_is_rejected(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError):
            validator.validate("STOPPED", "stop")

    def test_unknown_state_is_rejected(self, validator: StrategyControlValidator) -> None:
        with pytest.raises(ValueError):
            validator.validate("ARCHIVED", "start")

    def test_unknown_action_is_rejected(self, validator: StrategyControlValidator) -> None:
        with pytest.raises(ValueError):
            validator.validate("RUNNING", "restart")

    def test_error_message_names_the_transition(
        self, validator: StrategyControlValidator
    ) -> None:
        with pytest.raises(ValueError, match="STOPPED -> pause"):
            validator.validate("STOPPED", "pause")
