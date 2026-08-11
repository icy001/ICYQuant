"""Tests for OMSHealth — health monitoring and metrics."""

import unittest

from services.oms.observability.oms_health import OMSHealth, HealthStatus
from services.oms.observability.order_metrics import OrderMetrics
from services.oms.observability.execution_metrics import ExecutionMetrics
from services.oms.observability.recovery_metrics import RecoveryMetrics
from services.oms.observability.reconciliation_metrics import ReconciliationMetrics


class TestOMSHealth(unittest.TestCase):

    def setUp(self):
        self.health = OMSHealth()

    def test_initial_healthy(self):
        self.assertEqual(self.health.overall_status, HealthStatus.HEALTHY)

    def test_degraded_on_component_degraded(self):
        self.health.set_component_degraded("execution_gateway", "slow")
        self.assertEqual(self.health.overall_status, HealthStatus.DEGRADED)

    def test_unhealthy_on_critical_component_down(self):
        self.health.set_component_unhealthy("event_store", "corruption")
        self.assertEqual(self.health.overall_status, HealthStatus.UNHEALTHY)

    def test_degraded_on_non_critical_down(self):
        self.health.set_component_unhealthy("execution_gateway", "disconnected")
        self.assertEqual(self.health.overall_status, HealthStatus.DEGRADED)
        self.assertTrue(self.health.is_degraded_mode)

    def test_recovery_to_healthy(self):
        self.health.set_component_degraded("execution_gateway", "slow")
        self.health.set_component_healthy("execution_gateway")
        self.assertEqual(self.health.overall_status, HealthStatus.HEALTHY)

    def test_to_dict(self):
        d = self.health.to_dict()
        self.assertEqual(d["overall_status"], "Healthy")
        self.assertIn("components", d)
        self.assertIn("metrics", d)


class TestOrderMetrics(unittest.TestCase):

    def test_record_and_query(self):
        m = OrderMetrics()
        m.record_created()
        m.record_filled()
        m.record_submission_latency(0.012)
        d = m.to_dict()
        self.assertEqual(d["orders_created_total"], 1)
        self.assertEqual(d["orders_filled_total"], 1)
        self.assertAlmostEqual(d["avg_submission_latency"], 0.012)


class TestExecutionMetrics(unittest.TestCase):

    def test_record(self):
        m = ExecutionMetrics()
        m.record_request()
        m.record_ack()
        m.record_timeout()
        d = m.to_dict()
        self.assertEqual(d["execution_requests_total"], 1)
        self.assertEqual(d["execution_ack_total"], 1)
        self.assertEqual(d["execution_timeout_total"], 1)


class TestRecoveryMetrics(unittest.TestCase):

    def test_success_rate(self):
        m = RecoveryMetrics()
        m.record_recovery(True, 0.5)
        m.record_recovery(False, 1.0)
        self.assertAlmostEqual(m.recovery_success_rate, 0.5)


class TestReconciliationMetrics(unittest.TestCase):

    def test_consistency_rate(self):
        m = ReconciliationMetrics()
        m.record_reconciliation(True)
        m.record_reconciliation(False)
        m.record_reconciliation(True)
        self.assertAlmostEqual(m.consistency_rate, 2/3)


if __name__ == '__main__':
    unittest.main()
