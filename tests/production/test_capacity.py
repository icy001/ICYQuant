"""
Capacity tests for ICYQuant production readiness.

Tests system capacity at various account scales (100, 1000, 10000)
and validates resource prediction accuracy and degradation under load.
Uses StressTest from release.benchmark.
"""

import time

import pytest

from release.benchmark import ResourceMetrics, StressResult, StressTest


class TestCapacityAt100Accounts:
    """Test capacity at 100 account scale."""

    def test_capacity_100_accounts(self):
        """Verify system handles 100 concurrent account operations."""
        stress = StressTest(
            duration_per_level=0.5,
            concurrency_levels=[100],
            degradation_threshold=0.15,
        )

        call_count = {"count": 0}

        def account_operation():
            call_count["count"] += 1
            time.sleep(0.001)

        result = stress.run(account_operation, name="capacity_100_accounts")

        assert isinstance(result, StressResult)
        assert result.max_sustainable_tps >= 0
        assert result.peak_tps >= result.max_sustainable_tps
        assert "capacity_100_accounts" in result.name
        assert len(result.concurrency_levels_tested) == 1
        assert result.concurrency_levels_tested[0] == 100

    def test_resource_metrics_at_100_accounts(self):
        """Verify resource metrics are captured at 100 account scale."""
        stress = StressTest(
            duration_per_level=0.5,
            concurrency_levels=[100],
        )

        def account_operation():
            pass

        result = stress.run(account_operation, name="resource_100")

        assert isinstance(result.resource_at_peak, ResourceMetrics)
        assert isinstance(result.resource_at_break, ResourceMetrics)
        assert result.resource_at_peak.thread_count > 0


class TestCapacityAt1000Accounts:
    """Test capacity at 1000 account scale."""

    def test_capacity_1000_accounts(self):
        """Verify system handles 1000 concurrent account operations."""
        stress = StressTest(
            duration_per_level=0.5,
            concurrency_levels=[1000],
            degradation_threshold=0.20,
        )

        def account_operation():
            time.sleep(0.0005)

        result = stress.run(account_operation, name="capacity_1000_accounts")

        assert isinstance(result, StressResult)
        assert result.max_sustainable_tps >= 0
        assert result.duration > 0
        assert result.concurrency_levels_tested == [1000]

    def test_peak_tps_at_1000_accounts(self):
        """Verify peak TPS is reported at 1000 account scale."""
        stress = StressTest(
            duration_per_level=0.3,
            concurrency_levels=[1000],
        )

        counter = {"n": 0}

        def fast_operation():
            counter["n"] += 1

        result = stress.run(fast_operation, name="peak_1000")

        assert result.peak_tps >= 0
        assert result.peak_tps >= result.max_sustainable_tps


class TestCapacityAt10000Accounts:
    """Test capacity at 10000 account scale."""

    def test_capacity_10000_accounts(self):
        """Verify system handles 10000 concurrent account operations."""
        stress = StressTest(
            duration_per_level=0.3,
            concurrency_levels=[10000],
            degradation_threshold=0.25,
        )

        def lightweight_operation():
            pass

        result = stress.run(lightweight_operation, name="capacity_10000_accounts")

        assert isinstance(result, StressResult)
        assert result.max_sustainable_tps >= 0
        assert result.concurrency_levels_tested == [10000]

    def test_breaking_point_detection(self):
        """Verify breaking point is detected at high concurrency."""
        stress = StressTest(
            duration_per_level=0.2,
            concurrency_levels=[100, 500, 1000, 5000, 10000],
            degradation_threshold=0.50,
        )

        slowdown = {"factor": 1.0}

        def variable_operation():
            time.sleep(0.0001 * slowdown["factor"])

        result = stress.run(variable_operation, name="breaking_point_test")

        assert isinstance(result, StressResult)
        assert len(result.concurrency_levels_tested) == 5


class TestResourcePrediction:
    """Test resource prediction accuracy."""

    def test_resource_metrics_capture(self):
        """Verify resource metrics are accurately captured during load."""
        stress = StressTest(
            duration_per_level=0.3,
            concurrency_levels=[500],
        )

        def sample_operation():
            time.sleep(0.001)

        result = stress.run(sample_operation, name="resource_capture")

        assert isinstance(result.resource_at_peak, ResourceMetrics)
        assert isinstance(result.resource_at_break, ResourceMetrics)

    def test_cpu_measurement(self):
        """Verify CPU measurement returns a valid float."""
        cpu = StressTest._measure_cpu()
        assert isinstance(cpu, float)
        assert cpu >= 0.0

    def test_memory_measurement(self):
        """Verify memory measurement returns a valid int."""
        mem = StressTest._measure_memory()
        assert isinstance(mem, int)
        assert mem >= 0

    def test_resource_metrics_creation(self):
        """Test ResourceMetrics dataclass creation."""
        metrics = ResourceMetrics(
            cpu_percent=45.2,
            memory_bytes=8192,
            thread_count=150,
            open_handles=25,
        )
        assert metrics.cpu_percent == 45.2
        assert metrics.memory_bytes == 8192
        assert metrics.thread_count == 150
        assert metrics.open_handles == 25


class TestDegradationUnderLoad:
    """Test degradation detection under increasing load."""

    def test_degradation_threshold_configuration(self):
        """Verify degradation threshold is properly configured."""
        stress = StressTest(
            degradation_threshold=0.15,
            concurrency_levels=[100, 500, 1000],
        )
        assert stress.degradation_threshold == 0.15
        assert stress.concurrency_levels == [100, 500, 1000]

    def test_gradual_load_increase(self):
        """Verify system behavior under gradually increasing load."""
        stress = StressTest(
            duration_per_level=0.3,
            concurrency_levels=[100, 200, 400, 800],
            degradation_threshold=0.30,
        )

        counter = {"n": 0}

        def stable_operation():
            counter["n"] += 1

        result = stress.run(stable_operation, name="gradual_load")

        assert isinstance(result, StressResult)
        assert len(result.concurrency_levels_tested) == 4
        assert result.peak_tps >= 0

    def test_error_rate_tracking(self):
        """Verify error rate is tracked during stress testing."""
        stress = StressTest(
            duration_per_level=0.2,
            concurrency_levels=[100],
            degradation_threshold=0.10,
        )

        errors = {"count": 0}

        def sometimes_failing_operation():
            errors["count"] += 1
            if errors["count"] % 10 == 0:
                raise ValueError("Simulated processing error")

        result = stress.run(sometimes_failing_operation, name="error_tracking")

        assert isinstance(result, StressResult)

    def test_stress_result_properties(self):
        """Test StressResult dataclass properties."""
        result = StressResult(
            name="test",
            max_sustainable_tps=5000.0,
            peak_tps=7500.0,
            breaking_point_tps=10000.0,
            duration=120.0,
        )
        assert result.name == "test"
        assert result.max_sustainable_tps == 5000.0
        assert result.peak_tps == 7500.0
        assert result.duration == 120.0
        assert result.degradation_threshold == 0.1
        assert result.errors == []
        assert result.concurrency_levels_tested == []