"""Test Exposure Controller — exposure reduction behavior."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.exposure_controller import ExposureController


class TestExposureController:
    """Test exposure controller operations."""

    def test_initial_state(self):
        ec = ExposureController()
        assert ec._current_exposure == 0.0
        assert ec._max_allowed_exposure == 0.15

    def test_set_state(self):
        ec = ExposureController()
        ec.set_state(current_exposure=0.18, current_leverage=2.5)
        assert ec._current_exposure == 0.18

    def test_check_no_breach(self):
        ec = ExposureController()
        ec.set_state(0.10, 1.5)
        result = ec.check()
        assert not result["breached"]

    def test_check_exposure_breached(self):
        ec = ExposureController()
        ec.set_state(0.20, 1.5)
        result = ec.check()
        assert result["breached"]

    def test_check_leverage_breached(self):
        ec = ExposureController()
        ec.set_state(0.10, 3.0)
        result = ec.check()
        assert result["breached"]

    def test_reduce_exposure(self):
        ec = ExposureController()
        ec.set_state(0.18, 2.5)
        result = ec.reduce_exposure(
            target_exposure=0.10,
            reason="Governance freeze",
        )
        assert result["status"] == "INITIATED"
        assert result["final_exposure"] == 0.10
        assert result["success"]

    def test_reduce_with_default_steps(self):
        ec = ExposureController()
        result = ec.reduce_exposure(reason="Auto-reduce")
        assert "CANCEL_NEW_ORDERS" in result["steps_executed"]
        assert "STOP_NEW_ALLOCATION" in result["steps_executed"]
        assert "REDUCE_LEVERAGE" in result["steps_executed"]
        assert "REDUCE_EXPOSURE" in result["steps_executed"]

    def test_reduction_history(self):
        ec = ExposureController()
        ec.reduce_exposure(target_exposure=0.10, reason="Test 1")
        ec.reduce_exposure(target_exposure=0.08, reason="Test 2")
        history = ec.get_reduction_history()
        assert len(history) == 2

    def test_metrics(self):
        ec = ExposureController()
        ec.reduce_exposure(reason="Test")
        metrics = ec.get_metrics()
        assert metrics["reductions_applied"] == 1
