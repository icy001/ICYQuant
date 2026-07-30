"""
Chaos engineering tests for the ICYQuant production system.

Simulates various failure scenarios to test system resilience and
auto-recovery capabilities. Uses ChaosTest from release.benchmark
to inject failures and measure recovery.
"""

import time

import pytest

from release.benchmark import ChaosResult, ChaosScenario, ChaosTest


class TestBrokerDisconnection:
    """Test broker disconnection recovery scenarios."""

    def test_broker_disconnect_recovery(self):
        """Verify system recovers from broker disconnection within timeout."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        connected = {"status": True}

        def disconnect():
            connected["status"] = False

        def health_check():
            return connected["status"]

        def reconnect():
            connected["status"] = True

        result = chaos.test_broker_disconnect(
            disconnect_func=disconnect,
            health_check=health_check,
            reconnect_func=reconnect,
        )

        assert isinstance(result, ChaosResult)
        assert result.scenario == ChaosScenario.BROKER_DISCONNECT
        assert result.recovery_time >= 0
        assert result.consistency_check_passed is True

    def test_broker_disconnect_no_manual_reconnect(self):
        """Verify system detects persistent broker failure without reconnect."""
        chaos = ChaosTest(recovery_timeout=0.3, health_check_interval=0.05)

        connected = {"status": True}

        def disconnect():
            connected["status"] = False

        def health_check():
            return connected["status"]

        result = chaos.test_broker_disconnect(
            disconnect_func=disconnect,
            health_check=health_check,
        )

        assert result.success is False
        assert any("did not recover" in issue.lower() for issue in result.detected_issues)

    def test_broker_disconnect_injection_failure(self):
        """Verify injection failure is properly captured."""
        chaos = ChaosTest(recovery_timeout=0.5, health_check_interval=0.1)

        def failing_inject():
            raise RuntimeError("Simulated injection error")

        def health_check():
            return True

        result = chaos.test_broker_disconnect(
            disconnect_func=failing_inject,
            health_check=health_check,
        )

        assert any("Injection failed" in issue for issue in result.detected_issues)


class TestMessageQueueFailure:
    """Test message queue failure recovery."""

    def test_message_queue_failure_recovery(self):
        """Verify system recovers from message queue failure."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        mq_ok = {"status": True}

        def mq_fail():
            mq_ok["status"] = False

        def health_check():
            return mq_ok["status"]

        def mq_recover():
            mq_ok["status"] = True

        result = chaos.test_message_queue_failure(
            mq_fail_func=mq_fail,
            health_check=health_check,
            mq_recover_func=mq_recover,
        )

        assert isinstance(result, ChaosResult)
        assert result.scenario == ChaosScenario.MESSAGE_QUEUE_FAILURE
        assert result.success is True

    def test_message_queue_failure_timeout(self):
        """Verify timeout is reported when MQ does not recover."""
        chaos = ChaosTest(recovery_timeout=0.3, health_check_interval=0.05)

        mq_ok = {"status": True}

        def mq_fail():
            mq_ok["status"] = False

        def health_check():
            return mq_ok["status"]

        result = chaos.test_message_queue_failure(
            mq_fail_func=mq_fail,
            health_check=health_check,
        )

        assert result.success is False
        assert len(result.detected_issues) > 0


class TestCacheFailure:
    """Test Redis cache failure recovery."""

    def test_cache_failure_recovery(self):
        """Verify system recovers from Redis cache failure."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        cache_ok = {"status": True}

        def cache_fail():
            cache_ok["status"] = False

        def health_check():
            return cache_ok["status"]

        def cache_recover():
            cache_ok["status"] = True

        result = chaos.test_redis_cache_failure(
            redis_fail_func=cache_fail,
            health_check=health_check,
            redis_recover_func=cache_recover,
        )

        assert result.scenario == ChaosScenario.REDIS_CACHE_FAILURE
        assert result.success is True
        assert result.consistency_check_passed is True

    def test_cache_failure_detection(self):
        """Verify cache failure is detected and reported."""
        chaos = ChaosTest(recovery_timeout=0.3, health_check_interval=0.05)

        cache_ok = {"status": True}

        def cache_fail():
            cache_ok["status"] = False

        def health_check():
            return cache_ok["status"]

        result = chaos.test_redis_cache_failure(
            redis_fail_func=cache_fail,
            health_check=health_check,
        )

        assert result.success is False
        assert any("did not recover" in issue.lower() for issue in result.detected_issues)


class TestNetworkDegradation:
    """Test network degradation resilience."""

    def test_network_delay_recovery(self):
        """Verify system recovers after network delay injection is removed."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        network_ok = {"status": True}

        def inject_delay():
            network_ok["status"] = False

        def health_check():
            return network_ok["status"]

        def remove_delay():
            network_ok["status"] = True

        result = chaos.test_network_delay(
            delay_inject_func=inject_delay,
            health_check=health_check,
            delay_remove_func=remove_delay,
        )

        assert result.scenario == ChaosScenario.NETWORK_DELAY
        assert result.success is True
        assert result.recovery_time >= 0

    def test_network_degradation_resilience(self):
        """Verify system remains responsive during partial degradation."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        degraded = {"status": True}

        def inject_degradation():
            degraded["status"] = False

        def health_check():
            return degraded["status"]

        def remove_degradation():
            degraded["status"] = True

        result = chaos.test_network_delay(
            delay_inject_func=inject_degradation,
            health_check=health_check,
            delay_remove_func=remove_degradation,
        )

        assert result.success is True
        assert result.consistency_check_passed is True


class TestDatabaseFailure:
    """Test database failure recovery."""

    def test_database_crash_recovery(self):
        """Verify system recovers from database crash."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        db_ok = {"status": True}

        def db_crash():
            db_ok["status"] = False

        def health_check():
            return db_ok["status"]

        def db_recover():
            db_ok["status"] = True

        result = chaos.test_database_crash(
            db_crash_func=db_crash,
            health_check=health_check,
            db_recover_func=db_recover,
        )

        assert result.scenario == ChaosScenario.DATABASE_CRASH
        assert result.success is True

    def test_database_crash_without_recovery(self):
        """Verify database crash without recovery is detected."""
        chaos = ChaosTest(recovery_timeout=0.3, health_check_interval=0.05)

        db_ok = {"status": True}

        def db_crash():
            db_ok["status"] = False

        def health_check():
            return db_ok["status"]

        result = chaos.test_database_crash(
            db_crash_func=db_crash,
            health_check=health_check,
        )

        assert result.success is False
        assert len(result.detected_issues) > 0


class TestGPUFailure:
    """Test GPU failure resilience."""

    def test_gpu_failure_recovery(self):
        """Verify system recovers from GPU failure."""
        chaos = ChaosTest(recovery_timeout=5.0, health_check_interval=0.1)

        gpu_ok = {"status": True}

        def gpu_fail():
            gpu_ok["status"] = False

        def health_check():
            return gpu_ok["status"]

        def gpu_recover():
            gpu_ok["status"] = True

        result = chaos.test_gpu_failure(
            gpu_fail_func=gpu_fail,
            health_check=health_check,
            gpu_recover_func=gpu_recover,
        )

        assert result.scenario == ChaosScenario.GPU_FAILURE
        assert result.success is True

    def test_gpu_failure_timeout(self):
        """Verify GPU failure timeout detection."""
        chaos = ChaosTest(recovery_timeout=0.3, health_check_interval=0.05)

        gpu_ok = {"status": True}

        def gpu_fail():
            gpu_ok["status"] = False

        def health_check():
            return gpu_ok["status"]

        result = chaos.test_gpu_failure(
            gpu_fail_func=gpu_fail,
            health_check=health_check,
        )

        assert result.success is False
        assert any("did not recover" in issue.lower() for issue in result.detected_issues)


class TestChaosResultProperties:
    """Test ChaosResult dataclass properties."""

    def test_chaos_result_defaults(self):
        """Test ChaosResult default field values."""
        result = ChaosResult(
            scenario=ChaosScenario.BROKER_DISCONNECT,
            recovery_time=1.5,
            data_loss=False,
        )

        assert result.scenario == ChaosScenario.BROKER_DISCONNECT
        assert result.recovery_time == 1.5
        assert result.data_loss is False
        assert result.consistency_check_passed is True
        assert result.detected_issues == []
        assert result.mitigations_triggered == []
        assert result.duration == 0.0
        assert result.success is True

    def test_chaos_scenario_enum(self):
        """Test ChaosScenario enum values."""
        assert ChaosScenario.BROKER_DISCONNECT.value == "broker_disconnect"
        assert ChaosScenario.MESSAGE_QUEUE_FAILURE.value == "message_queue_failure"
        assert ChaosScenario.REDIS_CACHE_FAILURE.value == "redis_cache_failure"
        assert ChaosScenario.NETWORK_DELAY.value == "network_delay"
        assert ChaosScenario.DATABASE_CRASH.value == "database_crash"
        assert ChaosScenario.GPU_FAILURE.value == "gpu_failure"

    def test_chaos_test_custom_timeout(self):
        """Test ChaosTest initialization with custom timeout."""
        chaos = ChaosTest(recovery_timeout=10.0, health_check_interval=1.0)
        assert chaos.recovery_timeout == 10.0
        assert chaos.health_check_interval == 1.0

    def test_chaos_test_default_timeout(self):
        """Test ChaosTest default timeout values."""
        chaos = ChaosTest()
        assert chaos.recovery_timeout == 30.0
        assert chaos.health_check_interval == 0.5

    def test_consistency_check_static_method(self):
        """Test the static consistency check method."""
        passed, details = ChaosTest._check_consistency()
        assert passed is True
        assert "consistent" in details.lower()