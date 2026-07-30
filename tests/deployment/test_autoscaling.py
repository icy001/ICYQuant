"""
Tests for ICYQuant AutoScaler.
"""

import pytest
from datetime import datetime

from infrastructure.runtime.autoscaler import (
    AutoScaler,
    ScalingPolicy,
    ScaleDirection,
    ScalingStrategy,
    MetricSample,
)


class TestAutoScaler:
    """Test auto-scaling policies and evaluation."""

    def test_register_policy(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=2,
            max_replicas=10,
        )
        scaler.register_policy(policy, current_replicas=3)
        status = scaler.get_status()
        assert "cpu-scale" in status["policies"]

    def test_scale_up_on_high_cpu(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=2,
            max_replicas=10,
            scale_up_threshold=1.2,
        )
        scaler.register_policy(policy, current_replicas=3)
        for _ in range(5):
            scaler.record_metric("cpu_usage", 90.0)
        event = scaler.evaluate_policy("cpu-scale")
        assert event.direction == ScaleDirection.SCALE_UP

    def test_scale_down_on_low_cpu(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=2,
            max_replicas=10,
            scale_down_threshold=0.8,
        )
        scaler.register_policy(policy, current_replicas=8)
        for _ in range(5):
            scaler.record_metric("cpu_usage", 20.0)
        event = scaler.evaluate_policy("cpu-scale")
        assert event.direction == ScaleDirection.SCALE_DOWN

    def test_no_change_when_stable(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=2,
            max_replicas=10,
        )
        scaler.register_policy(policy, current_replicas=5)
        for _ in range(5):
            scaler.record_metric("cpu_usage", 65.0)
        event = scaler.evaluate_policy("cpu-scale")
        assert event.direction == ScaleDirection.NO_CHANGE

    def test_min_replicas_enforcement(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=5,
            max_replicas=10,
            scale_down_threshold=0.8,
        )
        scaler.register_policy(policy, current_replicas=5)
        for _ in range(5):
            scaler.record_metric("cpu_usage", 10.0)
        event = scaler.evaluate_policy("cpu-scale")
        assert event.new_replicas >= 5

    def test_max_replicas_enforcement(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=2,
            max_replicas=5,
            scale_up_threshold=1.2,
        )
        scaler.register_policy(policy, current_replicas=5)
        for _ in range(5):
            scaler.record_metric("cpu_usage", 95.0)
        event = scaler.evaluate_policy("cpu-scale")
        assert event.new_replicas <= 5

    def test_cooldown_period(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="cpu-scale",
            metric_name="cpu_usage",
            target_value=70.0,
            min_replicas=2,
            max_replicas=10,
            cooldown_seconds=3600,
        )
        scaler.register_policy(policy, current_replicas=3)
        for _ in range(5):
            scaler.record_metric("cpu_usage", 95.0)
        scaler.evaluate_policy("cpu-scale")
        event = scaler.evaluate_policy("cpu-scale")
        assert event.direction == ScaleDirection.NO_CHANGE

    def test_evaluate_all_policies(self):
        scaler = AutoScaler()
        scaler.register_policy(
            ScalingPolicy(name="cpu", metric_name="cpu", target_value=70.0),
            current_replicas=3,
        )
        scaler.register_policy(
            ScalingPolicy(name="mem", metric_name="mem", target_value=75.0),
            current_replicas=2,
        )
        events = scaler.evaluate_all()
        assert len(events) == 2

    def test_remove_policy(self):
        scaler = AutoScaler()
        scaler.register_policy(
            ScalingPolicy(name="cpu", metric_name="cpu", target_value=70.0),
            current_replicas=3,
        )
        scaler.remove_policy("cpu")
        status = scaler.get_status()
        assert "cpu" not in status["policies"]

    def test_gpu_queue_scaling(self):
        scaler = AutoScaler()
        policy = ScalingPolicy(
            name="gpu-queue",
            metric_name="inference_queue_depth",
            target_value=10.0,
            min_replicas=3,
            max_replicas=20,
        )
        scaler.register_policy(policy, current_replicas=3)
        for _ in range(10):
            scaler.record_metric("inference_queue_depth", 100.0)
        event = scaler.evaluate_policy("gpu-queue")
        assert event.direction == ScaleDirection.SCALE_UP

    def test_get_status(self):
        scaler = AutoScaler()
        scaler.register_policy(
            ScalingPolicy(name="cpu", metric_name="cpu", target_value=70.0),
            current_replicas=3,
        )
        status = scaler.get_status()
        assert status["totalEvents"] >= 0
        assert "cpu" in status["policies"]
        assert status["policies"]["cpu"]["currentReplicas"] == 3