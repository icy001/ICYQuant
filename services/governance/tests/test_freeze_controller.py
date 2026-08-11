"""Test Freeze Controller — freeze/unfreeze behavior."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.freeze_controller import FreezeController, FreezeScope


class TestFreezeController:
    """Test freeze controller operations."""

    def test_initial_state(self):
        fc = FreezeController()
        assert not fc.is_global_frozen

    def test_global_freeze(self):
        fc = FreezeController()
        result = fc.freeze(scope="GLOBAL", reason="Test")
        assert result["status"] == "FROZEN"
        assert fc.is_global_frozen
        assert fc.is_frozen(scope="GLOBAL")

    def test_global_unfreeze(self):
        fc = FreezeController()
        fc.freeze(scope="GLOBAL")
        fc.unfreeze(scope="GLOBAL")
        assert not fc.is_global_frozen

    def test_strategy_freeze(self):
        fc = FreezeController()
        fc.freeze(scope="STRATEGY", target="strat-A")
        assert fc.is_frozen(scope="STRATEGY", target="strat-A")
        assert not fc.is_frozen(scope="STRATEGY", target="strat-B")

    def test_strategy_unfreeze(self):
        fc = FreezeController()
        fc.freeze(scope="STRATEGY", target="strat-A")
        fc.unfreeze(scope="STRATEGY", target="strat-A")
        assert not fc.is_frozen(scope="STRATEGY", target="strat-A")

    def test_global_freeze_overrides_strategy(self):
        fc = FreezeController()
        fc.freeze(scope="GLOBAL")
        # Global freeze should make everything frozen
        assert fc.is_frozen(scope="STRATEGY", target="any")

    def test_targeted_freeze_does_not_affect_other(self):
        fc = FreezeController()
        fc.freeze(scope="ASSET", target="NVDA")
        assert fc.is_frozen(scope="ASSET", target="NVDA")
        assert not fc.is_frozen(scope="ASSET", target="TSLA")

    def test_cancel_pending(self):
        fc = FreezeController()
        result = fc.cancel_pending(reason="Test")
        assert result["status"] == "CANCELLED"

    def test_get_active_freezes(self):
        fc = FreezeController()
        fc.freeze(scope="GLOBAL")
        fc.freeze(scope="STRATEGY", target="strat-A")
        active = fc.get_active_freezes()
        assert active["GLOBAL"] is True
        assert "strat-A" in active["STRATEGY"]

    def test_metrics(self):
        fc = FreezeController()
        fc.freeze(scope="PORTFOLIO", target="pf-A")
        metrics = fc.get_metrics()
        assert metrics["total_freezes"] == 1
