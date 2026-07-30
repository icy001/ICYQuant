from services.observability import (
    AlertEngine,
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AlertEvaluator,
    NotificationDispatcher,
    NotificationChannel,
    NotificationConfig,
)


class TestAlertEvaluator:
    def test_greater_than(self):
        evaluator = AlertEvaluator()
        rule = AlertRule(
            rule_id="test",
            name="Test",
            metric_name="latency",
            condition="GT",
            threshold=100,
            severity="WARNING",
        )
        assert evaluator.evaluate(200, rule) is True
        assert evaluator.evaluate(50, rule) is False

    def test_less_than(self):
        evaluator = AlertEvaluator()
        rule = AlertRule(
            rule_id="test",
            name="Test",
            metric_name="memory",
            condition="LT",
            threshold=10,
            severity="CRITICAL",
        )
        assert evaluator.evaluate(5, rule) is True
        assert evaluator.evaluate(50, rule) is False

    def test_greater_or_equal(self):
        evaluator = AlertEvaluator()
        rule = AlertRule(
            rule_id="test",
            name="Test",
            metric_name="errors",
            condition="GTE",
            threshold=5,
            severity="WARNING",
        )
        assert evaluator.evaluate(5, rule) is True
        assert evaluator.evaluate(4.9, rule) is False


class TestAlertEngine:
    def test_add_rule(self):
        engine = AlertEngine()
        rule = AlertRule(
            rule_id="rule1",
            name="High Latency",
            metric_name="order_latency_ms",
            condition="GT",
            threshold=200,
            severity=AlertSeverity.WARNING.value,
        )
        engine.add_rule(rule)
        assert len(engine.list_rules()) == 1

    def test_evaluate_metric_triggers_alert(self):
        engine = AlertEngine()
        rule = AlertRule(
            rule_id="rule1",
            name="High Latency",
            metric_name="order_latency_ms",
            condition="GT",
            threshold=200,
            severity=AlertSeverity.WARNING.value,
        )
        engine.add_rule(rule)
        triggered = engine.evaluate_metric("order_latency_ms", 500)
        assert len(triggered) == 1
        assert triggered[0].severity == AlertSeverity.WARNING.value

    def test_evaluate_metric_no_alert(self):
        engine = AlertEngine()
        rule = AlertRule(
            rule_id="rule1",
            name="High Latency",
            metric_name="order_latency_ms",
            condition="GT",
            threshold=200,
            severity=AlertSeverity.WARNING.value,
        )
        engine.add_rule(rule)
        triggered = engine.evaluate_metric("order_latency_ms", 50)
        assert len(triggered) == 0

    def test_get_active_alerts(self):
        engine = AlertEngine()
        rule = AlertRule(
            rule_id="rule1",
            name="High Latency",
            metric_name="latency",
            condition="GT",
            threshold=200,
            severity=AlertSeverity.CRITICAL.value,
        )
        engine.add_rule(rule)
        engine.evaluate_metric("latency", 500)
        active = engine.get_active_alerts()
        assert len(active) == 1

    def test_acknowledge_alert(self):
        engine = AlertEngine()
        rule = AlertRule(
            rule_id="rule1",
            name="Test",
            metric_name="metric",
            condition="GT",
            threshold=100,
            severity="WARNING",
        )
        engine.add_rule(rule)
        triggered = engine.evaluate_metric("metric", 200)
        alert_id = triggered[0].alert_id
        engine.acknowledge_alert(alert_id)
        alerts = engine.get_active_alerts()
        assert len(alerts) == 0

    def test_resolve_alert(self):
        engine = AlertEngine()
        rule = AlertRule(
            rule_id="rule1",
            name="Test",
            metric_name="metric",
            condition="GT",
            threshold=100,
            severity="WARNING",
        )
        engine.add_rule(rule)
        triggered = engine.evaluate_metric("metric", 200)
        engine.resolve_alert(triggered[0].alert_id)
        history = engine.get_alert_history()
        assert len(history) > 0

    def test_multiple_rules(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", name="Warn", metric_name="latency",
            condition="GT", threshold=200, severity="WARNING",
        ))
        engine.add_rule(AlertRule(
            rule_id="r2", name="Critical", metric_name="latency",
            condition="GT", threshold=500, severity="CRITICAL",
        ))
        triggered = engine.evaluate_metric("latency", 600)
        assert len(triggered) == 2


class TestNotificationDispatcher:
    def test_configure_channel(self):
        dispatcher = NotificationDispatcher()
        config = NotificationConfig(
            channel=NotificationChannel.SLACK.value,
            target="#alerts",
            enabled=True,
        )
        dispatcher.configure_channel(NotificationChannel.SLACK.value, config)
        assert len(dispatcher._configs[NotificationChannel.SLACK.value]) == 1

    def test_send_notification(self):
        dispatcher = NotificationDispatcher()
        config = NotificationConfig(
            channel=NotificationChannel.EMAIL.value,
            target="ops@test.com",
            enabled=True,
        )
        dispatcher.configure_channel(NotificationChannel.EMAIL.value, config)

        alert = Alert(
            alert_id="alert1",
            rule_id="rule1",
            rule_name="Test",
            metric_name="latency",
            current_value=500,
            threshold=200,
            severity="CRITICAL",
            status="TRIGGERED",
            message="Test alert",
            timestamp=None,
        )
        dispatcher.send(alert, [NotificationChannel.EMAIL.value])
        sent = dispatcher.get_sent_notifications()
        assert len(sent) == 1
        assert sent[0]["channel"] == NotificationChannel.EMAIL.value
