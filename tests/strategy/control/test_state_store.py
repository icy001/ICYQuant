"""Tests for the strategy state store compare-and-set transitions."""

from __future__ import annotations

from services.strategy.control.state_store import (
    InMemoryStrategyStateStore,
    StrategyStateStore,
)


class TestStrategyStateStore:
    def test_unknown_strategy_defaults_to_stopped(self) -> None:
        store = InMemoryStrategyStateStore()
        assert store.get("STRAT-001") == "STOPPED"

    def test_set_then_get(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")
        assert store.get("STRAT-001") == "RUNNING"

    def test_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryStrategyStateStore(), StrategyStateStore)


class TestCompareAndSet:
    def test_successful_transition(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")

        assert store.transition("STRAT-001", "RUNNING", "PAUSING")
        assert store.get("STRAT-001") == "PAUSING"

    def test_failed_transition_keeps_state_unchanged(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")

        assert not store.transition("STRAT-001", "STOPPED", "STARTING")
        assert store.get("STRAT-001") == "RUNNING"

    def test_concurrent_transition_is_safe(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")

        first = store.transition("STRAT-001", "RUNNING", "PAUSING")
        second = store.transition("STRAT-001", "RUNNING", "STOPPING")

        assert first is True
        assert second is False
        assert store.get("STRAT-001") == "PAUSING"

    def test_second_worker_can_advance_from_new_state(self) -> None:
        store = InMemoryStrategyStateStore()
        store.set("STRAT-001", "RUNNING")

        assert store.transition("STRAT-001", "RUNNING", "PAUSING")
        assert store.transition("STRAT-001", "PAUSING", "PAUSED")
        assert store.get("STRAT-001") == "PAUSED"
