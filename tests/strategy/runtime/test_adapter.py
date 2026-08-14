"""Tests for the strategy runtime adapter seam."""

from __future__ import annotations

import pytest

from services.strategy.runtime.adapter import (
    RuntimeActionError,
    StrategyRuntimeAdapter,
)


class FakeAdapter:
    """A minimal concrete implementation of the adapter protocol."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.state = "STOPPED"
        self.fail_start = False

    def start(self, strategy_id: str) -> None:
        self.calls.append("start")
        if self.fail_start:
            raise RuntimeActionError("start failed")
        self.state = "READY"

    def pause(self, strategy_id: str) -> None:
        self.calls.append("pause")
        self.state = "RUNNING"

    def resume(self, strategy_id: str) -> None:
        self.calls.append("resume")
        self.state = "RUNNING"

    def stop(self, strategy_id: str) -> None:
        self.calls.append("stop")
        self.state = "STOPPED"

    def kill(self, strategy_id: str) -> None:
        self.calls.append("kill")
        self.state = "STOPPED"

    def can_resume(self, strategy_id: str) -> bool:
        self.calls.append("can_resume")
        return True

    def get_state(self, strategy_id: str) -> str:
        return self.state


class TestStrategyRuntimeAdapter:
    def test_concrete_adapter_satisfies_protocol(self) -> None:
        adapter = FakeAdapter()
        assert isinstance(adapter, StrategyRuntimeAdapter)

    def test_adapter_exposes_all_lifecycle_actions(self) -> None:
        adapter = FakeAdapter()

        adapter.start("STRAT-001")
        adapter.pause("STRAT-001")
        adapter.resume("STRAT-001")
        adapter.stop("STRAT-001")
        adapter.kill("STRAT-001")

        assert adapter.calls == [
            "start",
            "pause",
            "resume",
            "stop",
            "kill",
        ]

    def test_adapter_reports_runtime_state(self) -> None:
        adapter = FakeAdapter()
        adapter.start("STRAT-001")
        assert adapter.get_state("STRAT-001") == "READY"


class TestRuntimeActionError:
    def test_can_be_raised_and_caught(self) -> None:
        adapter = FakeAdapter()
        adapter.fail_start = True

        with pytest.raises(RuntimeActionError):
            adapter.start("STRAT-001")

        assert adapter.state == "STOPPED"
