"""Tests for Canary Release Manager."""
import pytest
from services.serving.canary import (
    CanaryManager, CanaryConfig, CanaryStage, RolloutState, CanaryStatus,
    _STAGE_TRAFFIC, _STAGE_ORDER,
)


class TestCanaryManager:
    def test_start_rollout(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38", new_model="mock_model")
        assert canary.status.state == RolloutState.ROLLING_OUT
        assert canary.status.traffic_share == 0.05
        assert canary.status.current_stage == CanaryStage.INITIAL

    def test_advance_stages(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        stages = [CanaryStage.INITIAL, CanaryStage.LOW, CanaryStage.MEDIUM, CanaryStage.HIGH, CanaryStage.FULL]
        for expected_stage in stages:
            assert canary.status.current_stage == expected_stage
            if expected_stage != CanaryStage.FULL:
                canary.advance()

    def test_complete_rollout(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        for _ in range(5):
            if canary.status.state != RolloutState.COMPLETED:
                canary.advance()
        assert canary.status.state == RolloutState.COMPLETED
        assert canary.status.traffic_share == 1.0

    def test_rollback(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        canary.rollback()
        assert canary.status.state == RolloutState.ROLLED_BACK
        assert canary.status.traffic_share == 0.0

    def test_pause_resume(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        canary.pause()
        assert canary.status.state == RolloutState.PAUSED
        canary.resume()
        assert canary.status.state == RolloutState.ROLLING_OUT

    def test_is_new_model_hash(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        assert canary.is_new_model(0.01) is True
        assert canary.is_new_model(0.5) is False

    def test_is_new_model_after_complete(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        for _ in range(5):
            if canary.status.state != RolloutState.COMPLETED:
                canary.advance()
        assert canary.is_new_model(0.95) is True

    def test_is_new_model_after_rollback(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        canary.rollback()
        assert canary.is_new_model(0.01) is False

    def test_health_check_healthy(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        canary.update_metrics({"error_rate": 0.001, "latency_p99_ms": 10.0})
        assert canary.health_check() is True

    def test_health_check_auto_rollback(self):
        canary = CanaryManager(CanaryConfig(
            min_duration_per_stage=0,
            auto_rollback=True,
            anomaly_thresholds={"error_rate": 0.01, "latency_p99_ms": 100.0},
        ))
        canary.start_rollout("alpha_v38")
        canary.update_metrics({"error_rate": 0.05})
        assert canary.health_check() is False
        assert canary.status.state == RolloutState.ROLLED_BACK

    def test_stage_traffic_mapping(self):
        assert _STAGE_TRAFFIC[CanaryStage.INITIAL] == 0.05
        assert _STAGE_TRAFFIC[CanaryStage.LOW] == 0.10
        assert _STAGE_TRAFFIC[CanaryStage.MEDIUM] == 0.25
        assert _STAGE_TRAFFIC[CanaryStage.HIGH] == 0.50
        assert _STAGE_TRAFFIC[CanaryStage.FULL] == 1.00

    def test_min_duration_enforced(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=3600))
        canary.start_rollout("alpha_v38")
        with pytest.raises(RuntimeError, match="Minimum stage duration"):
            canary.advance()

    def test_rollback_callbacks(self):
        callback_calls = []
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.add_rollback_callback(lambda name: callback_calls.append(name))
        canary.start_rollout("alpha_v38")
        canary.rollback()
        assert len(callback_calls) > 0

    def test_metrics_history(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        canary.update_metrics({"latency_p99_ms": 12.0})
        canary.update_metrics({"latency_p99_ms": 15.0})
        history = canary.get_metrics_history()
        assert len(history) == 2

    def test_reset(self):
        canary = CanaryManager(CanaryConfig(min_duration_per_stage=0))
        canary.start_rollout("alpha_v38")
        canary.reset()
        assert canary.status.state == RolloutState.IDLE
        assert canary.status.traffic_share == 0.0
