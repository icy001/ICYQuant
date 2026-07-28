"""Tests for AI Autonomous Trading Governor."""

import pytest
from datetime import date, time, datetime, timezone

from services.trading_governor import (
    BreakerScope,
    BreakerEvent,
    ComplianceAuthority,
    ComplianceResult,
    ComplianceStatus,
    EmergencyAction,
    EmergencyController,
    EmergencyEvent,
    GlobalCircuitBreaker,
    GovernanceMemory,
    HealthReport,
    HealthStatus,
    ModeTransition,
    Permission,
    PermissionDecision,
    RiskAuthorityController,
    RiskLimits,
    RuntimeMode,
    RuntimeModeManager,
    Strategy,
    StrategyCoordinator,
    StrategyStatus,
    SystemHealthMonitor,
    TradingGovernorService,
    TradingPermissionEngine,
)


# ---------------------------------------------------------------------------
# System Health Monitor
# ---------------------------------------------------------------------------

class TestSystemHealthMonitor:
    def test_evaluate_min(self):
        monitor = SystemHealthMonitor()
        metrics = {"cpu": 90, "memory": 85, "redis": 95, "kafka": 100}
        assert monitor.evaluate(metrics) == 85.0

    def test_evaluate_empty(self):
        monitor = SystemHealthMonitor()
        assert monitor.evaluate({}) == 100.0

    def test_weighted_evaluate(self):
        monitor = SystemHealthMonitor()
        metrics = {"cpu": 50, "redis": 100}
        weights = {"cpu": 0.7, "redis": 0.3}
        score = monitor.weighted_evaluate(metrics, weights)
        assert score == pytest.approx(50 * 0.7 + 100 * 0.3)

    def test_status_healthy(self):
        monitor = SystemHealthMonitor()
        assert monitor.status(90) == HealthStatus.HEALTHY
        assert monitor.status(80) == HealthStatus.HEALTHY

    def test_status_degraded(self):
        monitor = SystemHealthMonitor()
        assert monitor.status(75) == HealthStatus.DEGRADED
        assert monitor.status(60) == HealthStatus.DEGRADED

    def test_status_unhealthy(self):
        monitor = SystemHealthMonitor()
        assert monitor.status(55) == HealthStatus.UNHEALTHY
        assert monitor.status(0) == HealthStatus.UNHEALTHY

    def test_evaluate_full(self):
        monitor = SystemHealthMonitor()
        metrics = {"cpu": 95, "memory": 50, "redis": 50, "kafka": 50, "database": 50}
        report = monitor.evaluate_full(metrics)
        assert report.status == HealthStatus.UNHEALTHY
        assert len(report.details["unhealthy_components"]) >= 2
        assert "cpu" in report.details["healthy_components"]

    def test_is_trading_safe(self):
        monitor = SystemHealthMonitor()
        assert monitor.is_trading_safe(80) is True
        assert monitor.is_trading_safe(55) is False
        assert monitor.is_trading_safe(70, min_threshold=75) is False


# ---------------------------------------------------------------------------
# Trading Permission Engine
# ---------------------------------------------------------------------------

class TestTradingPermission:
    def test_allow(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=95, risk_ok=True, compliance_ok=True)
        assert result == "ALLOW"

    def test_block_health(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=55, risk_ok=True, compliance_ok=True)
        assert result == "BLOCK"

    def test_block_compliance(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=95, risk_ok=True, compliance_ok=False)
        assert result == "BLOCK"

    def test_block_market_closed(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=95, risk_ok=True, compliance_ok=True, market_open=False)
        assert result == "BLOCK"

    def test_block_circuit_breaker(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=95, risk_ok=True, compliance_ok=True, circuit_breaker_active=True)
        assert result == "BLOCK"

    def test_limit(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=95, risk_ok=False, compliance_ok=True)
        assert result == "LIMIT"

    def test_pause_health(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=70, risk_ok=True, compliance_ok=True)
        assert result == "PAUSE"

    def test_pause_confidence(self):
        engine = TradingPermissionEngine()
        result = engine.decide(health=95, risk_ok=True, compliance_ok=True, confidence=0.4)
        assert result == "PAUSE"

    def test_decide_full(self):
        engine = TradingPermissionEngine()
        decision = engine.decide_full(health=95, risk_ok=True, compliance_ok=True)
        assert decision.permission == Permission.ALLOW
        assert "All checks passed" in decision.reason

    def test_decide_full_block(self):
        engine = TradingPermissionEngine()
        decision = engine.decide_full(health=50, risk_ok=True, compliance_ok=True)
        assert decision.permission == Permission.BLOCK
        assert "health critical" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Global Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_trigger_global(self):
        cb = GlobalCircuitBreaker()
        event = cb.trigger(reason="Market crash")
        assert cb.active is True
        assert event.scope == BreakerScope.GLOBAL

    def test_reset(self):
        cb = GlobalCircuitBreaker()
        cb.trigger()
        cb.reset()
        assert cb.active is False

    def test_scoped_breaker(self):
        cb = GlobalCircuitBreaker()
        cb.trigger(BreakerScope.SYMBOL, "NVDA", "Too volatile")
        assert cb.is_symbol_blocked("NVDA") is True
        assert cb.is_symbol_blocked("AAPL") is False

    def test_global_overrides_scoped(self):
        cb = GlobalCircuitBreaker()
        cb.trigger(BreakerScope.SYMBOL, "NVDA")
        cb.trigger(BreakerScope.GLOBAL, "all")
        assert cb.is_symbol_blocked("NVDA") is True  # global overrides

    def test_strategy_blocked(self):
        cb = GlobalCircuitBreaker()
        cb.trigger(BreakerScope.STRATEGY, "momentum", "drawdown limit")
        assert cb.is_strategy_blocked("momentum") is True
        assert cb.is_strategy_blocked("mean_reversion") is False

    def test_kill_switch(self):
        cb = GlobalCircuitBreaker()
        event = cb.kill_switch("Emergency")
        assert cb.active is True
        assert event.triggered_by == "kill_switch"

    def test_get_active_breakers(self):
        cb = GlobalCircuitBreaker()
        cb.trigger(BreakerScope.SYMBOL, "NVDA")
        cb.trigger(BreakerScope.BROKER, "broker1")
        assert len(cb.get_active_breakers()) == 2


# ---------------------------------------------------------------------------
# Strategy Coordinator
# ---------------------------------------------------------------------------

class TestStrategyCoordinator:
    def test_register(self):
        coord = StrategyCoordinator()
        s = Strategy(name="momentum", priority=5)
        coord.register(s)
        assert coord.get("momentum") is not None
        assert coord.strategy_count == 1

    def test_unregister(self):
        coord = StrategyCoordinator()
        s = Strategy(name="momentum", priority=5)
        coord.register(s)
        removed = coord.unregister("momentum")
        assert removed.name == "momentum"
        assert coord.strategy_count == 0

    def test_allocate_sort(self):
        coord = StrategyCoordinator()
        s1 = Strategy(name="low", priority=1)
        s2 = Strategy(name="high", priority=10)
        s3 = Strategy(name="mid", priority=5)
        sorted_list = coord.allocate([s1, s2, s3])
        assert sorted_list[0].name == "high"
        assert sorted_list[1].name == "mid"
        assert sorted_list[2].name == "low"

    def test_allocate_resources(self):
        coord = StrategyCoordinator()
        coord.register(Strategy(name="a", priority=3))
        coord.register(Strategy(name="b", priority=1))
        alloc = coord.allocate_resources(1000)
        assert alloc["a"] == 750.0
        assert alloc["b"] == 250.0

    def test_pause_and_resume_all(self):
        coord = StrategyCoordinator()
        coord.register(Strategy(name="a", priority=3))
        coord.register(Strategy(name="b", priority=1))
        coord.pause_all()
        assert len(coord.get_active_strategies()) == 0
        coord.resume_all()
        assert len(coord.get_active_strategies()) == 2

    def test_set_status(self):
        coord = StrategyCoordinator()
        coord.register(Strategy(name="a", priority=3))
        assert coord.set_status("a", StrategyStatus.STOPPED) is True
        assert coord.get("a").status == StrategyStatus.STOPPED
        assert coord.set_status("nonexistent", StrategyStatus.ACTIVE) is False

    def test_get_status_summary(self):
        coord = StrategyCoordinator()
        coord.register(Strategy(name="a", priority=3))
        coord.register(Strategy(name="b", priority=1))
        coord.set_status("b", StrategyStatus.STOPPED)
        summary = coord.get_status_summary()
        assert summary["ACTIVE"] == 1
        assert summary["STOPPED"] == 1


# ---------------------------------------------------------------------------
# Risk Authority Controller
# ---------------------------------------------------------------------------

class TestRiskAuthority:
    def test_leverage_limit_high_risk(self):
        rc = RiskAuthorityController()
        assert rc.leverage_limit(0.9) == 1

    def test_leverage_limit_medium_risk(self):
        rc = RiskAuthorityController()
        assert rc.leverage_limit(0.6) == 2

    def test_leverage_limit_low_risk(self):
        rc = RiskAuthorityController()
        assert rc.leverage_limit(0.2) == 5

    def test_position_limit(self):
        rc = RiskAuthorityController()
        assert rc.position_limit(0.9, 100) == 25.0
        assert rc.position_limit(0.6, 100) == 50.0
        assert rc.position_limit(0.4, 100) == 75.0
        assert rc.position_limit(0.2, 100) == 100.0

    def test_daily_loss_limit(self):
        rc = RiskAuthorityController()
        assert rc.daily_loss_limit(0.9, 1000) == 300.0
        assert rc.daily_loss_limit(0.6, 1000) == 600.0
        assert rc.daily_loss_limit(0.2, 1000) == 1000.0

    def test_adjust_all(self):
        rc = RiskAuthorityController()
        limits = rc.adjust_all(risk_score=0.7, base_position=100, base_exposure=200, base_loss=1000)
        assert limits.leverage_limit == 2
        assert limits.max_position == 50.0
        assert limits.daily_loss_limit == 600.0
        assert limits.margin_requirement == 0.3

    def test_adjustment_history(self):
        rc = RiskAuthorityController()
        rc.adjust_all(0.3, 100, 200, 1000)
        rc.adjust_all(0.7, 100, 200, 1000)
        assert rc.adjustment_count == 2


# ---------------------------------------------------------------------------
# Compliance Authority
# ---------------------------------------------------------------------------

class TestComplianceAuthority:
    def test_validate_basic(self):
        ca = ComplianceAuthority()
        assert ca.validate(True) is True
        assert ca.validate(False) is False

    def test_check_symbol(self):
        ca = ComplianceAuthority()
        ca.add_restricted_symbol("TSLA")
        assert ca.check_symbol("NVDA").status == ComplianceStatus.PASS
        assert ca.check_symbol("TSLA").status == ComplianceStatus.FAIL
        assert ca.check_symbol("tsla").status == ComplianceStatus.FAIL  # case-insensitive

    def test_check_holiday(self):
        ca = ComplianceAuthority()
        ca.add_market_holiday(date(2026, 1, 1))
        assert ca.check_holiday(date(2026, 1, 1)).status == ComplianceStatus.FAIL
        assert ca.check_holiday(date(2026, 1, 2)).status == ComplianceStatus.PASS

    def test_check_session(self):
        ca = ComplianceAuthority()
        ca.set_trading_session(time(9, 30), time(16, 0))
        in_session = datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc)
        out_session = datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc)
        assert ca.check_session(in_session).status == ComplianceStatus.PASS
        assert ca.check_session(out_session).status == ComplianceStatus.FAIL

    def test_check_session_no_config(self):
        ca = ComplianceAuthority()
        result = ca.check_session()
        assert result.status == ComplianceStatus.PASS  # always allowed when not configured

    def test_validate_all(self):
        ca = ComplianceAuthority()
        ca.add_restricted_symbol("TSLA")
        results = ca.validate_all("NVDA")
        assert all(r.status == ComplianceStatus.PASS for r in results)

    def test_is_approved(self):
        ca = ComplianceAuthority()
        ca.add_restricted_symbol("TSLA")
        assert ca.is_approved("NVDA") is True
        assert ca.is_approved("TSLA") is False

    def test_counts(self):
        ca = ComplianceAuthority()
        ca.add_restricted_symbol("A")
        ca.add_restricted_symbol("B")
        ca.add_market_holiday(date(2026, 1, 1))
        assert ca.restricted_count == 2
        assert ca.holiday_count == 1


# ---------------------------------------------------------------------------
# Emergency Controller
# ---------------------------------------------------------------------------

class TestEmergencyController:
    def test_kill_switch(self):
        ec = EmergencyController()
        result = ec.kill_switch()
        assert result == "STOP_ALL"
        assert ec.is_active is True
        assert ec.current_action == EmergencyAction.KILL_SWITCH

    def test_emergency_liquidate(self):
        ec = EmergencyController()
        result = ec.emergency_liquidate("Margin call")
        assert result == "LIQUIDATE_ALL"

    def test_emergency_pause(self):
        ec = EmergencyController()
        result = ec.emergency_pause()
        assert result == "PAUSE_ALL"

    def test_restart(self):
        ec = EmergencyController()
        ec.kill_switch()
        result = ec.restart()
        assert result == "RESTART"
        assert ec.is_active is False
        assert ec.current_action is None

    def test_reset(self):
        ec = EmergencyController()
        ec.kill_switch()
        ec.reset()
        assert ec.is_active is False

    def test_event_log(self):
        ec = EmergencyController()
        ec.kill_switch()
        ec.restart()
        assert ec.event_count == 2
        log = ec.get_event_log()
        assert log[-1].action == EmergencyAction.EMERGENCY_RESTART


# ---------------------------------------------------------------------------
# Runtime Mode Manager
# ---------------------------------------------------------------------------

class TestRuntimeModeManager:
    def test_default_mode(self):
        rm = RuntimeModeManager()
        assert rm.current_mode == RuntimeMode.PAPER

    def test_switch_string(self):
        rm = RuntimeModeManager()
        rm.switch("simulation")
        assert rm.current_mode_value == "simulation"

    def test_valid_transition(self):
        rm = RuntimeModeManager()
        rm.switch("simulation")
        rm.switch("live")
        assert rm.current_mode == RuntimeMode.LIVE

    def test_invalid_transition(self):
        rm = RuntimeModeManager()
        # PAPER → LIVE is not allowed directly
        result = rm.switch("live")
        assert rm.current_mode == RuntimeMode.PAPER  # unchanged

    def test_safe_mode_from_any(self):
        rm = RuntimeModeManager(RuntimeMode.LIVE)
        rm.safe_mode("Emergency")
        assert rm.is_safe() is True

    def test_can_switch_to(self):
        rm = RuntimeModeManager()
        assert rm.can_switch_to("simulation") is True
        assert rm.can_switch_to("live") is False  # PAPER → LIVE not allowed

    def test_is_live(self):
        rm = RuntimeModeManager(RuntimeMode.PAPER)
        assert rm.is_live() is False
        rm.switch("simulation")
        rm.switch("live")
        assert rm.is_live() is True

    def test_transition_history(self):
        rm = RuntimeModeManager()
        rm.switch("simulation")
        rm.switch("shadow")
        assert rm.transition_count == 2


# ---------------------------------------------------------------------------
# Governance Memory
# ---------------------------------------------------------------------------

class TestGovernanceMemory:
    def test_record(self):
        gm = GovernanceMemory()
        gm.record({"type": "test", "data": "hello"})
        assert gm.event_count == 1

    def test_record_permission(self):
        gm = GovernanceMemory()
        gm.record_permission("ALLOW", "all ok")
        events = gm.query_by_type("permission")
        assert len(events) == 1
        assert events[0]["permission"] == "ALLOW"

    def test_record_breaker(self):
        gm = GovernanceMemory()
        gm.record_breaker("global", "all", "trigger", "crash")
        events = gm.query_by_type("circuit_breaker")
        assert len(events) == 1

    def test_record_emergency(self):
        gm = GovernanceMemory()
        gm.record_emergency("kill_switch", "manual")
        events = gm.query_by_type("emergency")
        assert len(events) == 1

    def test_record_mode_change(self):
        gm = GovernanceMemory()
        gm.record_mode_change("paper", "simulation", "testing")
        events = gm.query_by_type("mode_change")
        assert len(events) == 1

    def test_query_recent(self):
        gm = GovernanceMemory()
        for i in range(5):
            gm.record({"type": "test", "seq": i})
        recent = gm.query_recent(n=3)
        assert len(recent) == 3

    def test_clear(self):
        gm = GovernanceMemory()
        gm.record({"type": "test"})
        gm.clear()
        assert gm.event_count == 0

    def test_timestamp_auto_added(self):
        gm = GovernanceMemory()
        event = gm.record({"type": "test"})
        assert "timestamp" in event


# ---------------------------------------------------------------------------
# Trading Governor Service (integration)
# ---------------------------------------------------------------------------

class TestTradingGovernorService:
    def test_authorize_allow(self):
        service = TradingGovernorService(TradingPermissionEngine())
        assert service.authorize(95, True, True) == "ALLOW"

    def test_authorize_block(self):
        service = TradingGovernorService(TradingPermissionEngine())
        assert service.authorize(50, True, True) == "BLOCK"

    def test_authorize_full_pipeline(self):
        service = TradingGovernorService(TradingPermissionEngine())
        report = service.authorize_full(
            health_metrics={"cpu": 95, "memory": 90, "redis": 88, "kafka": 92, "database": 85, "broker_api": 90, "exchange_feed": 87},
            risk_ok=True,
            compliance_ok=True,
            confidence=0.85,
            market_open=True,
            symbol="NVDA",
            risk_score=0.3,
        )
        assert report["permission"] == "ALLOW"
        assert "health" in report
        assert "circuit_breaker" in report
        assert "compliance" in report
        assert "risk_limits" in report
        assert "runtime" in report
        assert "decision" in report
        # Memory should have recorded
        assert service.memory.event_count == 1

    def test_authorize_full_degraded_health(self):
        service = TradingGovernorService(TradingPermissionEngine())
        report = service.authorize_full(
            health_metrics={"cpu": 70, "memory": 70, "redis": 70},
            risk_ok=True,
            compliance_ok=True,
        )
        assert report["permission"] == "PAUSE"

    def test_authorize_full_with_breaker(self):
        service = TradingGovernorService(TradingPermissionEngine())
        service.circuit_breaker.kill_switch("Test")
        report = service.authorize_full(
            health_metrics={"cpu": 95, "memory": 95},
            risk_ok=True,
            compliance_ok=True,
        )
        assert report["permission"] == "BLOCK"
        assert report["circuit_breaker"]["active"] is True

    def test_kill_switch(self):
        service = TradingGovernorService(TradingPermissionEngine())
        report = service.kill_switch("Emergency test")
        assert report["action"] == "kill_switch"
        assert service.circuit_breaker.active is True
        assert service.emergency.is_active is True
        assert service.runtime.is_safe() is True

    def test_register_strategy(self):
        service = TradingGovernorService(TradingPermissionEngine())
        s = service.register_strategy("momentum", priority=5)
        assert s.name == "momentum"
        assert service.coordinator.strategy_count == 1


# ---------------------------------------------------------------------------
# Original minimal test from spec
# ---------------------------------------------------------------------------

def test_permission():
    service = TradingGovernorService(TradingPermissionEngine())
    assert service.authorize(95, True, True) == "ALLOW"
