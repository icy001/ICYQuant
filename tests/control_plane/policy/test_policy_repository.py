"""Unit tests: PolicyRepository persistence and audit log."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.policy.policy import Policy
from services.control_plane.policy.policy_condition import condition
from services.control_plane.policy.policy_context import PolicyContext
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import PolicyEngine
from services.control_plane.policy.policy_priority import PolicyPriority
from services.control_plane.policy.policy_rule import PolicyRule
from services.control_plane.repositories.policy_repository import (
    PolicyRepository,
)


def _policy() -> Policy:
    return Policy(
        "trading-safety-policy",
        "1.0.0",
        "Trading Safety Policy",
        priority=PolicyPriority.HIGH,
    ).add_rule(
        PolicyRule(
            rule_id="trading-halted-block",
            condition=condition(
                "trading_state", "equals", "TRADING_HALTED"
            ),
            decision=PolicyDecision.HALT,
            priority=PolicyPriority.HIGH,
        )
    )


class TestPolicyStore:
    def test_save_and_get(self):
        repo = PolicyRepository()
        repo.save_policy(_policy())
        restored = repo.get_policy("trading-safety-policy")
        assert restored is not None
        assert restored.policy_version == "1.0.0"
        assert len(restored.rules) == 1

    def test_get_version(self):
        repo = PolicyRepository()
        repo.save_policy(_policy())
        assert repo.get_policy_version("trading-safety-policy") == "1.0.0"
        assert repo.get_policy_version("missing") is None

    def test_count_and_list(self):
        repo = PolicyRepository()
        repo.save_policy(_policy())
        repo.save_policy(
            Policy("other-policy", "2.0.0", "Other")
        )
        assert repo.policy_count() == 2
        assert {p.policy_id for p in repo.list_policies()} == {
            "trading-safety-policy",
            "other-policy",
        }

    def test_delete(self):
        repo = PolicyRepository()
        repo.save_policy(_policy())
        assert repo.delete_policy("trading-safety-policy") is True
        assert repo.delete_policy("trading-safety-policy") is False

    def test_upsert_replaces_version(self):
        repo = PolicyRepository()
        repo.save_policy(_policy())
        repo.save_policy(Policy("trading-safety-policy", "1.1.0", "New"))
        assert repo.get_policy_version("trading-safety-policy") == "1.1.0"


class TestEvaluationLog:
    def _evaluation(self):
        engine = PolicyEngine()
        engine.register_policy(_policy())
        return engine.evaluate(
            PolicyContext(trading_state="TRADING_HALTED"),
            correlation_id="trace-1",
        )

    def test_record_and_count(self):
        repo = PolicyRepository()
        record_id = repo.record_evaluation(self._evaluation())
        assert record_id.startswith("PE-")
        assert repo.evaluation_count() == 1

    def test_get_evaluation(self):
        repo = PolicyRepository()
        record_id = repo.record_evaluation(self._evaluation())
        payload = repo.get_evaluation(record_id)
        assert payload is not None
        assert payload["decision"] == "HALT"
        assert payload["correlation_id"] == "trace-1"

    def test_get_evaluations_paginated(self):
        repo = PolicyRepository()
        repo.record_evaluation(self._evaluation())
        repo.record_evaluation(self._evaluation())
        repo.record_evaluation(self._evaluation())
        page = repo.get_evaluations(offset=1, limit=1)
        assert len(page) == 1
        assert len(repo.get_evaluations()) == 3

    def test_snapshot_restore_round_trip(self):
        repo = PolicyRepository()
        repo.save_policy(_policy())
        repo.record_evaluation(self._evaluation())

        restored = PolicyRepository()
        restored.restore(repo.snapshot())
        assert restored.policy_count() == 1
        assert restored.evaluation_count() == 1
        assert restored.get_policy_version("trading-safety-policy") == "1.0.0"
