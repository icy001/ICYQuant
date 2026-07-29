"""Tests for Alert Rule Engine, Notifier, and Escalation."""

import time

from services.monitoring.alert.rule_engine import (
    AlertRuleEngine,
    AlertRule,
    AlertSeverity,
    AlertState,
    Alert,
)
from services.monitoring.alert.notifier import (
    AlertNotifier,
    NotificationChannel,
    ChannelConfig,
)
from services.monitoring.alert.escalation import (
    EscalationManager,
    EscalationPolicy,
    EscalationLevel,
)


# =========================================================================
# Alert Rule Engine Tests
# =========================================================================


class TestAlertRule:
    """Tests for AlertRule."""

    def test_rule_fires_when_condition_met(self):
        rule = AlertRule(
            name="high_drawdown",
            description="Drawdown > 10%",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: m.get("drawdown_pct", 0) > 10.0,
            category="risk",
        )
        assert rule.evaluate({"drawdown_pct": 15.0}) is True
        assert rule.evaluate({"drawdown_pct": 5.0}) is False

    def test_disabled_rule_never_fires(self):
        rule = AlertRule(
            name="disabled_rule",
            description="Should not fire",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: True,
            enabled=False,
        )
        assert rule.evaluate({}) is False

    def test_rule_with_missing_key(self):
        rule = AlertRule(
            name="missing_key",
            description="Key may be missing",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: m.get("missing_key", 0) > 5,
        )
        assert rule.evaluate({}) is False

    def test_rule_exception_returns_false(self):
        rule = AlertRule(
            name="broken",
            description="Broken condition",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: m["nonexistent"],
        )
        assert rule.evaluate({}) is False


class TestAlert:
    """Tests for Alert dataclass."""

    def test_alert_lifecycle(self):
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.WARNING,
            message="Test alert",
        )
        assert alert.state == AlertState.FIRING

        alert.acknowledge("operator")
        assert alert.state == AlertState.ACKNOWLEDGED
        assert alert.acknowledged_by == "operator"

    def test_alert_resolve(self):
        alert = Alert(rule_name="test", severity=AlertSeverity.WARNING, message="test")
        alert.resolve()
        assert alert.state == AlertState.RESOLVED
        assert alert.resolved_at is not None

    def test_alert_suppress(self):
        alert = Alert(rule_name="test", severity=AlertSeverity.WARNING, message="test")
        alert.suppress()
        assert alert.state == AlertState.SUPPRESSED

    def test_alert_duration(self):
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message="test",
            fired_at=time.time() - 60,
        )
        duration = alert.duration_seconds()
        assert 58 <= duration <= 62

    def test_alert_to_dict(self):
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.CRITICAL,
            category="risk",
            message="High risk detected",
        )
        d = alert.to_dict()
        assert d["rule_name"] == "test_rule"
        assert d["severity"] == "critical"
        assert d["category"] == "risk"
        assert d["state"] == "firing"


class TestAlertRuleEngine:
    """Tests for AlertRuleEngine."""

    def test_add_and_list_rules(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="rule1",
            description="desc",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
        ))
        assert len(engine.list_rules()) == 1
        assert engine.get_rule("rule1") is not None

    def test_remove_rule(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="rule1",
            description="desc",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
        ))
        engine.remove_rule("rule1")
        assert len(engine.list_rules()) == 0

    def test_evaluate_triggers_alert(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="high_var",
            description="VaR too high",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: m.get("var", 0) > 5.0,
            category="risk",
            cooldown_seconds=0,
        ))

        alerts = engine.evaluate({"var": 8.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high_var"
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_evaluate_no_trigger(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="high_var",
            description="VaR too high",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: m.get("var", 0) > 5.0,
            cooldown_seconds=0,
        ))

        alerts = engine.evaluate({"var": 2.0})
        assert len(alerts) == 0

    def test_auto_resolve_when_condition_clears(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="high_var",
            description="VaR too high",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: m.get("var", 0) > 5.0,
            cooldown_seconds=0,
        ))

        # Fire
        engine.evaluate({"var": 8.0})
        active = engine.get_active_alerts()
        assert len(active) == 1

        # Resolve
        engine.evaluate({"var": 2.0})
        active = engine.get_active_alerts()
        assert len(active) == 0

        history = engine.get_alert_history()
        assert history[-1].state == AlertState.RESOLVED

    def test_cooldown_prevents_refire(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="test",
            description="desc",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
            cooldown_seconds=3600,  # 1 hour cooldown
        ))

        # First fire should work
        alerts1 = engine.evaluate({})
        assert len(alerts1) == 1

        # Second fire within cooldown should not fire
        alerts2 = engine.evaluate({})
        assert len(alerts2) == 0

    def test_get_active_alerts_by_severity(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="warn1",
            description="warn",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))
        engine.add_rule(AlertRule(
            name="crit1",
            description="crit",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))

        engine.evaluate({})
        assert len(engine.get_active_alerts(severity=AlertSeverity.CRITICAL)) == 1
        assert len(engine.get_active_alerts(severity=AlertSeverity.WARNING)) == 1
        assert len(engine.get_active_alerts(severity=AlertSeverity.INFO)) == 0

    def test_get_active_alerts_by_category(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="risk_alert",
            description="risk",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
            category="risk",
            cooldown_seconds=0,
        ))
        engine.add_rule(AlertRule(
            name="trading_alert",
            description="trading",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
            category="trading",
            cooldown_seconds=0,
        ))

        engine.evaluate({})
        assert len(engine.get_active_alerts(category="risk")) == 1
        assert len(engine.get_active_alerts(category="trading")) == 1
        assert len(engine.get_active_alerts(category="infra")) == 0

    def test_acknowledge_alert(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="test",
            description="desc",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))
        alerts = engine.evaluate({})
        alert_id = alerts[0].alert_id

        assert engine.acknowledge_alert(alert_id, "ops_team") is True
        assert engine.acknowledge_alert("nonexistent") is False

    def test_alert_summary(self):
        engine = AlertRuleEngine()
        engine.add_rule(AlertRule(
            name="crit1",
            description="crit",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))
        engine.evaluate({})
        summary = engine.get_alert_summary()
        assert summary["active_count"] == 1
        assert summary["by_severity"]["critical"] == 1


# =========================================================================
# Notifier Tests
# =========================================================================


class TestAlertNotifier:
    """Tests for AlertNotifier."""

    def test_add_and_list_channels(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="ops_console",
            channel_type=NotificationChannel.CONSOLE,
        ))
        channels = notifier.list_channels()
        assert len(channels) == 1
        assert channels[0].name == "ops_console"

    def test_remove_channel(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="ops_console",
            channel_type=NotificationChannel.CONSOLE,
        ))
        notifier.remove_channel("ops_console")
        assert len(notifier.list_channels()) == 0

    def test_send_console_notification(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="console",
            channel_type=NotificationChannel.CONSOLE,
        ))
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message="Test console alert",
        )
        notifications = notifier.send(alert, channel_names=["console"])
        assert len(notifications) == 1
        assert notifications[0].success is True
        assert notifications[0].channel_type == NotificationChannel.CONSOLE

    def test_severity_filter(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="critical_only",
            channel_type=NotificationChannel.CONSOLE,
            severity_filter=[AlertSeverity.CRITICAL],
        ))

        warning_alert = Alert(
            rule_name="warn",
            severity=AlertSeverity.WARNING,
            message="warning",
        )
        critical_alert = Alert(
            rule_name="crit",
            severity=AlertSeverity.CRITICAL,
            message="critical",
        )

        # Warning should be filtered out
        results = notifier.send(warning_alert, channel_names=["critical_only"])
        assert len(results) == 0

        # Critical should pass
        results = notifier.send(critical_alert, channel_names=["critical_only"])
        assert len(results) == 1
        assert results[0].success is True

    def test_disabled_channel_skipped(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="disabled_ch",
            channel_type=NotificationChannel.CONSOLE,
            enabled=False,
        ))
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message="test",
        )
        notifications = notifier.send(alert, channel_names=["disabled_ch"])
        assert len(notifications) == 0

    def test_send_batch(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="console",
            channel_type=NotificationChannel.CONSOLE,
        ))
        alerts = [
            Alert(rule_name="a1", severity=AlertSeverity.WARNING, message="m1"),
            Alert(rule_name="a2", severity=AlertSeverity.CRITICAL, message="m2"),
        ]
        notifications = notifier.send_batch(alerts, channel_names=["console"])
        assert len(notifications) == 2
        assert all(n.success for n in notifications)

    def test_get_history(self):
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="console",
            channel_type=NotificationChannel.CONSOLE,
        ))
        alert = Alert(rule_name="test", severity=AlertSeverity.WARNING, message="test")
        notifier.send(alert, channel_names=["console"])
        history = notifier.get_history()
        assert len(history) == 1


# =========================================================================
# Escalation Manager Tests
# =========================================================================


class TestEscalationManager:
    """Tests for EscalationManager."""

    def test_add_and_list_policies(self):
        mgr = EscalationManager()
        mgr.add_policy(EscalationPolicy(
            name="critical",
            levels=[
                EscalationLevel(delay_seconds=0, channels=["console"]),
                EscalationLevel(delay_seconds=300, channels=["slack"]),
            ],
        ))
        assert len(mgr.list_policies()) == 1

    def test_remove_policy(self):
        mgr = EscalationManager()
        mgr.add_policy(EscalationPolicy(name="test", levels=[]))
        mgr.remove_policy("test")
        assert len(mgr.list_policies()) == 0

    def test_escalation_on_time(self):
        mgr = EscalationManager()
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="slack",
            channel_type=NotificationChannel.CONSOLE,
        ))

        mgr.add_policy(EscalationPolicy(
            name="critical_policy",
            severity_filter=[AlertSeverity.CRITICAL],
            levels=[
                EscalationLevel(delay_seconds=0, channels=["slack"]),
            ],
        ))

        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.CRITICAL,
            message="test",
            fired_at=time.time() - 10,  # 10 seconds ago
        )

        escalated = mgr.check_escalations([alert], notifier)
        assert len(escalated) == 1
        assert alert.alert_id in escalated

    def test_no_escalation_before_delay(self):
        mgr = EscalationManager()
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="slack",
            channel_type=NotificationChannel.CONSOLE,
        ))

        mgr.add_policy(EscalationPolicy(
            name="delayed",
            severity_filter=[AlertSeverity.CRITICAL],
            levels=[
                EscalationLevel(delay_seconds=3600, channels=["slack"]),
            ],
        ))

        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.CRITICAL,
            message="test",
            fired_at=time.time(),  # Just now
        )

        escalated = mgr.check_escalations([alert], notifier)
        assert len(escalated) == 0

    def test_severity_filter(self):
        mgr = EscalationManager()
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="console",
            channel_type=NotificationChannel.CONSOLE,
        ))

        mgr.add_policy(EscalationPolicy(
            name="critical_only",
            severity_filter=[AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY],
            levels=[
                EscalationLevel(delay_seconds=0, channels=["console"]),
            ],
        ))

        warning_alert = Alert(
            rule_name="warn",
            severity=AlertSeverity.WARNING,
            message="test",
            fired_at=time.time() - 10,
        )

        escalated = mgr.check_escalations([warning_alert], notifier)
        assert len(escalated) == 0

    def test_category_filter(self):
        mgr = EscalationManager()
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="console",
            channel_type=NotificationChannel.CONSOLE,
        ))

        mgr.add_policy(EscalationPolicy(
            name="risk_only",
            category_filter=["risk"],
            levels=[
                EscalationLevel(delay_seconds=0, channels=["console"]),
            ],
        ))

        risk_alert = Alert(
            rule_name="r",
            severity=AlertSeverity.CRITICAL,
            message="test",
            category="risk",
            fired_at=time.time() - 10,
        )
        trading_alert = Alert(
            rule_name="t",
            severity=AlertSeverity.CRITICAL,
            message="test",
            category="trading",
            fired_at=time.time() - 10,
        )

        escalated = mgr.check_escalations([risk_alert, trading_alert], notifier)
        assert len(escalated) == 1

    def test_disabled_policy(self):
        mgr = EscalationManager()
        notifier = AlertNotifier()

        mgr.add_policy(EscalationPolicy(
            name="disabled",
            enabled=False,
            levels=[EscalationLevel(delay_seconds=0, channels=["console"])],
        ))

        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.CRITICAL,
            message="test",
            fired_at=time.time() - 10,
        )

        escalated = mgr.check_escalations([alert], notifier)
        assert len(escalated) == 0

    def test_reset_escalation(self):
        mgr = EscalationManager()
        notifier = AlertNotifier()
        notifier.add_channel(ChannelConfig(
            name="console",
            channel_type=NotificationChannel.CONSOLE,
        ))

        mgr.add_policy(EscalationPolicy(
            name="test",
            levels=[EscalationLevel(delay_seconds=0, channels=["console"])],
        ))

        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message="test",
            fired_at=time.time() - 10,
        )

        mgr.check_escalations([alert], notifier)
        assert mgr.get_escalation_state(alert.alert_id) == 0

        mgr.reset_escalation(alert.alert_id)
        assert mgr.get_escalation_state(alert.alert_id) == -1

    def test_get_status(self):
        mgr = EscalationManager()
        mgr.add_policy(EscalationPolicy(
            name="test",
            levels=[EscalationLevel(delay_seconds=0, channels=["console"])],
        ))
        status = mgr.get_status()
        assert status["policies_count"] == 1
