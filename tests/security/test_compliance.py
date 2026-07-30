"""
Tests for ICYQuant Compliance Center and Policy Engine.
"""

import pytest

from services.security.compliance import (
    ComplianceCenter,
    ComplianceFramework,
    ComplianceStatus,
)
from services.security.policy_engine import (
    PolicyEngine,
    Policy,
    PolicyStatement,
    PolicyCondition,
    PolicyEffect,
)


class TestComplianceCenter:
    """Test multi-framework compliance checking."""

    def test_get_check_catalog(self):
        cc = ComplianceCenter()
        catalog = cc.get_check_catalog()
        assert "sec" in catalog
        assert "gdpr" in catalog
        assert "iso27001" in catalog

    def test_run_framework_checks(self):
        cc = ComplianceCenter()
        checks = cc.run_framework_checks(ComplianceFramework.GDPR)
        assert len(checks) > 0
        assert checks[0].framework == ComplianceFramework.GDPR

    def test_generate_report(self):
        cc = ComplianceCenter()
        report = cc.generate_report([ComplianceFramework.ISO27001, ComplianceFramework.SOC2])
        assert report.overall_status in (ComplianceStatus.PASS, ComplianceStatus.WARNING, ComplianceStatus.FAIL)
        assert len(report.checks) > 0

    def test_generate_all_frameworks_report(self):
        cc = ComplianceCenter()
        report = cc.generate_report()
        assert report is not None
        assert len(report.checks) > 0

    def test_custom_check_registration(self):
        cc = ComplianceCenter()
        cc.register_check(
            ComplianceFramework.CUSTOM,
            "custom_check_1",
            "Custom Check",
            "A custom compliance check",
            lambda: ComplianceStatus.PASS,
        )
        results = cc.run_framework_checks(ComplianceFramework.CUSTOM)
        assert len(results) >= 1

    def test_report_to_dict(self):
        cc = ComplianceCenter()
        report = cc.generate_report([ComplianceFramework.SEC])
        report_dict = report.to_dict()
        assert "id" in report_dict
        assert "checks" in report_dict

    def test_get_status(self):
        cc = ComplianceCenter()
        status = cc.to_dict()
        assert "frameworks" in status


class TestPolicyEngine:
    """Test OPA-compatible policy engine."""

    def setup_method(self):
        self.engine = PolicyEngine()

    def test_create_policy(self):
        policy = Policy(
            name="Test Policy",
            enabled=True,
            priority=10,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition("user.role", "eq", "admin"),
                    ],
                ),
            ],
        )
        self.engine.create_policy(policy)
        policies = self.engine.list_policies()
        assert len(policies) == 1

    def test_evaluate_policy_allow(self):
        policy = Policy(
            name="Admin Allow",
            enabled=True,
            priority=10,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition("user.role", "eq", "admin"),
                    ],
                ),
            ],
        )
        self.engine.create_policy(policy)
        decision = self.engine.evaluate({"user": {"role": "admin"}})
        assert decision.decision == PolicyEffect.ALLOW

    def test_evaluate_policy_deny(self):
        policy = Policy(
            name="Deny Production Delete",
            enabled=True,
            priority=50,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.DENY,
                    conditions=[
                        PolicyCondition("environment", "eq", "production"),
                        PolicyCondition("action", "eq", "delete"),
                    ],
                ),
            ],
        )
        self.engine.create_policy(policy)
        decision = self.engine.evaluate({"environment": "production", "action": "delete"})
        assert decision.decision == PolicyEffect.DENY

    def test_evaluate_default_deny(self):
        decision = self.engine.evaluate({"user": "unknown"})
        assert decision.decision == PolicyEffect.DENY

    def test_update_policy(self):
        policy = Policy(name="Update Test", enabled=True)
        self.engine.create_policy(policy)
        self.engine.update_policy("Update Test", enabled=False)
        updated = self.engine.get_policy("Update Test")
        assert updated.enabled is False

    def test_delete_policy(self):
        policy = Policy(name="Delete Test", enabled=True)
        self.engine.create_policy(policy)
        self.engine.delete_policy("Delete Test")
        assert self.engine.get_policy("Delete Test") is None

    def test_condition_operators(self):
        conditions = [
            PolicyCondition("age", "gt", 18),
            PolicyCondition("status", "eq", "active"),
        ]
        ctx = {"age": 25, "status": "active"}
        for cond in conditions:
            assert cond.evaluate(ctx) is True

    def test_evaluate_decision_log(self):
        self.engine.evaluate({"test": 1})
        self.engine.evaluate({"test": 2})
        log = self.engine.get_decision_log()
        assert len(log) >= 2

    def test_get_status(self):
        policy = Policy(name="Status Test", enabled=True)
        self.engine.create_policy(policy)
        status = self.engine.to_dict()
        assert status["totalPolicies"] == 1
        assert status["activePolicies"] == 1
