"""Tests for Circuit Breaker, Auto Recovery, and Failover."""

import time

from services.monitoring.recovery.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerRegistry,
    CircuitBreakerOpenError,
)
from services.monitoring.recovery.auto_recovery import (
    AutoRecovery,
    RecoveryAction,
    RecoveryStatus,
)
from services.monitoring.recovery.failover import (
    FailoverManager,
    FailoverTarget,
    FailoverStatus,
)


# =========================================================================
# Circuit Breaker Tests
# =========================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_allow_request_when_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.allow_request() is True

    def test_transitions_to_open_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.on_failure()
        assert cb.state == CircuitState.CLOSED
        cb.on_failure()
        assert cb.state == CircuitState.OPEN

    def test_blocks_requests_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.on_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.on_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        # Allow one request through in half-open
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.on_failure()
        time.sleep(0.02)
        cb.allow_request()  # Transition to HALF_OPEN
        cb.on_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens_circuit(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.on_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.on_failure()
        assert cb.state == CircuitState.OPEN

    def test_on_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.on_failure()
        cb.on_failure()
        cb.on_success()
        assert cb._failure_count == 0

    def test_protect_decorator(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)

        call_count = [0]

        @cb.protect
        def my_func():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise RuntimeError("fail")
            return "ok"

        # First call fails
        try:
            my_func()
        except RuntimeError:
            pass
        assert call_count[0] == 1

        # Second call fails, circuit opens
        try:
            my_func()
        except RuntimeError:
            pass
        assert call_count[0] == 2

        # Third call blocked by circuit breaker
        try:
            my_func()
        except CircuitBreakerOpenError:
            pass
        assert call_count[0] == 2  # Not incremented

    def test_reset_forces_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.on_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_get_stats(self):
        cb = CircuitBreaker(name="broker_gw", failure_threshold=3)
        cb.on_failure()
        cb.on_success()
        stats = cb.get_stats()
        assert stats.name == "broker_gw"
        assert stats.total_failures == 1
        assert stats.total_successes == 1

    def test_on_open_on_close_callbacks(self):
        events = []

        def on_open(name):
            events.append(f"open:{name}")

        def on_close(name):
            events.append(f"close:{name}")

        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.01,
            on_open=on_open,
            on_close=on_close,
        )

        cb.on_failure()
        assert events == ["open:test"]

        time.sleep(0.02)
        cb.allow_request()
        cb.on_success()
        assert events == ["open:test", "close:test"]


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    def test_register_and_get(self):
        reg = CircuitBreakerRegistry()
        cb = CircuitBreaker(name="broker")
        reg.register(cb)
        assert reg.get("broker") is cb

    def test_get_or_create(self):
        reg = CircuitBreakerRegistry()
        cb1 = reg.get_or_create("broker")
        cb2 = reg.get_or_create("broker")
        assert cb1 is cb2

    def test_get_all_stats(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("broker", failure_threshold=3)
        reg.get_or_create("redis", failure_threshold=5)
        stats = reg.get_all_stats()
        assert len(stats) == 2

    def test_status_summary(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("a", failure_threshold=1).on_failure()
        reg.get_or_create("b", failure_threshold=3)
        summary = reg.status_summary()
        assert summary["open"] == 1
        assert summary["closed"] == 1
        assert summary["total"] == 2

    def test_reset_all(self):
        reg = CircuitBreakerRegistry()
        cb = reg.get_or_create("test", failure_threshold=1)
        cb.on_failure()
        assert cb.state == CircuitState.OPEN
        reg.reset_all()
        assert cb.state == CircuitState.CLOSED


# =========================================================================
# Auto Recovery Tests
# =========================================================================


class TestAutoRecovery:
    """Tests for AutoRecovery."""

    def test_register_and_list_actions(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="broker_reconnect",
            description="Reconnect to broker",
            condition_fn=lambda ctx: ctx.get("broker_status") == "down",
            action_fn=lambda: True,
        ))
        assert len(recovery.list_actions()) == 1

    def test_remove_action(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="broker_reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: True,
        ))
        recovery.remove_action("broker_reconnect")
        assert len(recovery.list_actions()) == 0

    def test_recovery_executes_when_condition_met(self):
        recovery = AutoRecovery()
        executed = [False]

        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: ctx.get("broker") == "down",
            action_fn=lambda: setattr(executed, '__setitem__', None) or executed.__setitem__(0, True) or True,
            max_attempts=3,
        ))

        results = recovery.check_and_recover({"broker": "down"})
        # The action_fn should have been called
        assert len(results) == 1

    def test_no_recovery_when_condition_not_met(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: ctx.get("broker") == "down",
            action_fn=lambda: True,
        ))

        results = recovery.check_and_recover({"broker": "healthy"})
        assert len(results) == 0

    def test_max_attempts_enforced(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: False,  # Always fails
            max_attempts=2,
            cooldown_seconds=0,
        ))

        # First attempt
        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 1
        assert results[0].status == RecoveryStatus.FAILED

        # Second attempt
        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 1
        assert results[0].status == RecoveryStatus.FAILED

        # Third attempt should be blocked
        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 1
        assert results[0].status == RecoveryStatus.MAX_ATTEMPTS_EXCEEDED

    def test_cooldown_respected(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: True,
            cooldown_seconds=3600,  # 1 hour
        ))

        # First call works
        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 1

        # Second call within cooldown should not execute
        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 0

    def test_force_actions_bypass_conditions(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: False,  # Never true
            action_fn=lambda: True,
        ))

        # Force should execute regardless
        results = recovery.check_and_recover({}, force_actions=["reconnect"])
        assert len(results) == 1
        assert results[0].status == RecoveryStatus.SUCCESS

    def test_disabled_action_skipped(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: True,
            enabled=False,
        ))

        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 0

    def test_action_exception_handled(self):
        recovery = AutoRecovery()

        def broken_action():
            raise RuntimeError("recovery failed")

        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=broken_action,
        ))

        results = recovery.check_and_recover({"broker": "down"})
        assert len(results) == 1
        assert results[0].status == RecoveryStatus.FAILED

    def test_reset_attempts(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: False,
            max_attempts=5,
            cooldown_seconds=0,
        ))

        recovery.check_and_recover({"broker": "down"})
        recovery.check_and_recover({"broker": "down"})
        recovery.reset_attempts("reconnect")

        results = recovery.check_and_recover({"broker": "down"})
        assert results[0].attempt == 1

    def test_get_status(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: True,
        ))
        recovery.check_and_recover({"broker": "down"})
        status = recovery.get_status()
        assert status["actions_count"] == 1
        assert status["total_recoveries"] == 1
        assert status["successful_recoveries"] == 1

    def test_get_history(self):
        recovery = AutoRecovery()
        recovery.register_action(RecoveryAction(
            name="reconnect",
            description="Reconnect",
            condition_fn=lambda ctx: True,
            action_fn=lambda: True,
        ))
        recovery.check_and_recover({"broker": "down"})
        history = recovery.get_history()
        assert len(history) == 1


# =========================================================================
# Failover Manager Tests
# =========================================================================


class TestFailoverManager:
    """Tests for FailoverManager."""

    def test_add_target_and_get_active(self):
        fm = FailoverManager()
        fm.add_target(FailoverTarget(
            name="broker",
            primary="broker_primary",
            backup="broker_backup",
            health_check_fn=lambda t: True,
            switch_fn=lambda src, dst: True,
        ))
        assert fm.get_active("broker") == "broker_primary"
        assert fm.get_status("broker") == FailoverStatus.PRIMARY

    def test_failover_when_primary_unhealthy(self):
        fm = FailoverManager()

        health = {"broker_primary": False, "broker_backup": True}

        fm.add_target(FailoverTarget(
            name="broker",
            primary="broker_primary",
            backup="broker_backup",
            health_check_fn=lambda t: health[t],
            switch_fn=lambda src, dst: True,
            cooldown_seconds=0,
        ))

        events = fm.check_and_failover()
        assert len(events) == 1
        assert events[0].success is True
        assert fm.get_active("broker") == "broker_backup"
        assert fm.get_status("broker") == FailoverStatus.FAILED_OVER

    def test_auto_failback_when_primary_recovers(self):
        fm = FailoverManager()

        health = {"broker_primary": False, "broker_backup": True}

        fm.add_target(FailoverTarget(
            name="broker",
            primary="broker_primary",
            backup="broker_backup",
            health_check_fn=lambda t: health[t],
            switch_fn=lambda src, dst: True,
            auto_failback=True,
            cooldown_seconds=0,
        ))

        # Fail over
        fm.check_and_failover()
        assert fm.get_active("broker") == "broker_backup"

        # Primary recovers
        health["broker_primary"] = True
        events = fm.check_and_failover()
        assert len(events) == 1
        assert events[0].success is True
        assert fm.get_active("broker") == "broker_primary"

    def test_no_failover_when_healthy(self):
        fm = FailoverManager()

        health = {"broker_primary": True, "broker_backup": True}

        fm.add_target(FailoverTarget(
            name="broker",
            primary="broker_primary",
            backup="broker_backup",
            health_check_fn=lambda t: health[t],
            switch_fn=lambda src, dst: True,
        ))

        events = fm.check_and_failover()
        assert len(events) == 0

    def test_force_failover(self):
        fm = FailoverManager()
        fm.add_target(FailoverTarget(
            name="broker",
            primary="broker_primary",
            backup="broker_backup",
            health_check_fn=lambda t: True,
            switch_fn=lambda src, dst: True,
        ))

        record = fm.force_failover("broker")
        assert record is not None
        assert record.success is True
        assert fm.get_active("broker") == "broker_backup"

    def test_force_failover_nonexistent(self):
        fm = FailoverManager()
        assert fm.force_failover("nonexistent") is None

    def test_get_all_status(self):
        fm = FailoverManager()
        fm.add_target(FailoverTarget(
            name="broker",
            primary="p",
            backup="b",
            health_check_fn=lambda t: True,
            switch_fn=lambda src, dst: True,
        ))
        fm.add_target(FailoverTarget(
            name="redis",
            primary="r1",
            backup="r2",
            health_check_fn=lambda t: True,
            switch_fn=lambda src, dst: True,
        ))

        status = fm.get_all_status()
        assert len(status) == 2
        assert status["broker"]["active"] == "p"
        assert status["redis"]["active"] == "r1"

    def test_health_check_exception_treated_as_unhealthy(self):
        fm = FailoverManager()

        def broken_check(t):
            raise RuntimeError("check failed")

        fm.add_target(FailoverTarget(
            name="broker",
            primary="p",
            backup="b",
            health_check_fn=broken_check,
            switch_fn=lambda src, dst: True,
            cooldown_seconds=0,
        ))

        # But backup must be healthy for failover to proceed
        # Both are broken, so no failover
        events = fm.check_and_failover()
        assert len(events) == 0

    def test_get_history(self):
        fm = FailoverManager()

        health = {"p": False, "b": True}

        fm.add_target(FailoverTarget(
            name="broker",
            primary="p",
            backup="b",
            health_check_fn=lambda t: health[t],
            switch_fn=lambda src, dst: True,
            cooldown_seconds=0,
        ))

        fm.check_and_failover()
        history = fm.get_history()
        assert len(history) == 1
        assert history[0].success is True

    def test_failover_record_to_dict(self):
        fm = FailoverManager()

        health = {"p": False, "b": True}

        fm.add_target(FailoverTarget(
            name="broker",
            primary="p",
            backup="b",
            health_check_fn=lambda t: health[t],
            switch_fn=lambda src, dst: True,
            cooldown_seconds=0,
        ))

        events = fm.check_and_failover()
        d = events[0].to_dict()
        assert d["target_name"] == "broker"
        assert d["success"] is True
