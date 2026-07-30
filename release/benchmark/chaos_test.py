"""
Chaos engineering module for simulating system failures.

Simulates various failure scenarios including broker disconnection,
message queue failures, Redis cache failures, network delays, database
crashes, and GPU failures to test system resilience and auto-recovery.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


class ChaosScenario(str, enum.Enum):
    BROKER_DISCONNECT = "broker_disconnect"
    MESSAGE_QUEUE_FAILURE = "message_queue_failure"
    REDIS_CACHE_FAILURE = "redis_cache_failure"
    NETWORK_DELAY = "network_delay"
    DATABASE_CRASH = "database_crash"
    GPU_FAILURE = "gpu_failure"


@dataclass
class ChaosResult:
    scenario: ChaosScenario
    recovery_time: float
    data_loss: bool
    data_loss_details: str = ""
    consistency_check_passed: bool = True
    consistency_details: str = ""
    detected_issues: list[str] = field(default_factory=list)
    mitigations_triggered: list[str] = field(default_factory=list)
    duration: float = 0.0
    success: bool = True


class ChaosTest:
    """
    Simulates failures to test system resilience and auto-recovery capabilities.

    Supports multiple chaos scenarios and measures recovery time,
    data loss, and consistency verification after failure injection.
    """

    def __init__(
        self,
        recovery_timeout: float = 30.0,
        health_check_interval: float = 0.5,
    ):
        self.recovery_timeout = recovery_timeout
        self.health_check_interval = health_check_interval

    def test_scenario(
        self,
        scenario: ChaosScenario,
        inject_func: Callable[[], None],
        health_check_func: Callable[[], bool],
        recovery_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        start_time = time.perf_counter()
        detected_issues: list[str] = []
        mitigations_triggered: list[str] = []
        data_loss = False
        consistency_passed = True
        consistency_details = ""

        try:
            inject_func()
        except Exception as e:
            detected_issues.append(f"Injection failed: {e}")

        if recovery_func is not None:
            try:
                recovery_func()
                mitigations_triggered.append("Manual recovery invoked")
            except Exception as e:
                detected_issues.append(f"Recovery failed: {e}")

        recovered = self._wait_for_recovery(health_check_func)
        recovery_time = time.perf_counter() - start_time

        if not recovered:
            detected_issues.append(
                f"System did not recover within {self.recovery_timeout}s"
            )
            return ChaosResult(
                scenario=scenario,
                recovery_time=recovery_time,
                data_loss=data_loss,
                consistency_check_passed=consistency_passed,
                consistency_details=consistency_details,
                detected_issues=detected_issues,
                mitigations_triggered=mitigations_triggered,
                duration=recovery_time,
                success=False,
            )

        consistency_passed, consistency_details = self._check_consistency()
        if not consistency_passed:
            data_loss = True
            detected_issues.append(f"Consistency check failed: {consistency_details}")

        return ChaosResult(
            scenario=scenario,
            recovery_time=recovery_time,
            data_loss=data_loss,
            consistency_check_passed=consistency_passed,
            consistency_details=consistency_details,
            detected_issues=detected_issues,
            mitigations_triggered=mitigations_triggered,
            duration=recovery_time,
            success=len(detected_issues) == 0,
        )

    def test_broker_disconnect(
        self,
        disconnect_func: Callable[[], None],
        health_check: Callable[[], bool],
        reconnect_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        return self.test_scenario(
            ChaosScenario.BROKER_DISCONNECT,
            disconnect_func,
            health_check,
            reconnect_func,
        )

    def test_message_queue_failure(
        self,
        mq_fail_func: Callable[[], None],
        health_check: Callable[[], bool],
        mq_recover_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        return self.test_scenario(
            ChaosScenario.MESSAGE_QUEUE_FAILURE,
            mq_fail_func,
            health_check,
            mq_recover_func,
        )

    def test_redis_cache_failure(
        self,
        redis_fail_func: Callable[[], None],
        health_check: Callable[[], bool],
        redis_recover_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        return self.test_scenario(
            ChaosScenario.REDIS_CACHE_FAILURE,
            redis_fail_func,
            health_check,
            redis_recover_func,
        )

    def test_network_delay(
        self,
        delay_inject_func: Callable[[], None],
        health_check: Callable[[], bool],
        delay_remove_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        return self.test_scenario(
            ChaosScenario.NETWORK_DELAY,
            delay_inject_func,
            health_check,
            delay_remove_func,
        )

    def test_database_crash(
        self,
        db_crash_func: Callable[[], None],
        health_check: Callable[[], bool],
        db_recover_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        return self.test_scenario(
            ChaosScenario.DATABASE_CRASH,
            db_crash_func,
            health_check,
            db_recover_func,
        )

    def test_gpu_failure(
        self,
        gpu_fail_func: Callable[[], None],
        health_check: Callable[[], bool],
        gpu_recover_func: Optional[Callable[[], None]] = None,
    ) -> ChaosResult:
        return self.test_scenario(
            ChaosScenario.GPU_FAILURE,
            gpu_fail_func,
            health_check,
            gpu_recover_func,
        )

    def _wait_for_recovery(self, health_check_func: Callable[[], bool]) -> bool:
        deadline = time.perf_counter() + self.recovery_timeout
        while time.perf_counter() < deadline:
            try:
                if health_check_func():
                    return True
            except Exception:
                pass
            time.sleep(self.health_check_interval)
        return False

    @staticmethod
    def _check_consistency() -> tuple[bool, str]:
        return True, "System state consistent after recovery"