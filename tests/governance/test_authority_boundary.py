"""Authority boundary (Commit 28 Part 1.4).

- Delegated Authority ⊆ Delegator Authority（不能越权）。
- Role Authority 不等于无限权限：Authority + Policy + Context = Effective Authority。
- Approval Snapshot 只用于 Audit（Snapshot != Current Authority）。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import Approval
from services.governance.approval_engine import GovernanceApprovalEngine
from services.governance.approval_rule import ApprovalRule
from services.governance.authority import (
    Authority,
    AuthorityResolver,
    AuthoritySnapshot,
    AuthoritySource,
)
from services.governance.condition import ConditionOperator, PolicyCondition
from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceEngine,
)
from services.governance.delegation import (
    AuthorityDelegation,
    DelegationAuthorityValidator,
)
from services.governance.models import Principal
from services.governance.permission import Permission
from services.governance.policy import Policy
from services.governance.registry import build_standard_governance
from services.governance.role import Role

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_delegation(**overrides):
    base = dict(
        delegation_id="DEL-001",
        delegator_id="commander-001",
        delegate_id="delegate-001",
        resource="trading",
        actions=("pause",),
        valid_from=NOW - timedelta(hours=1),
        valid_until=NOW + timedelta(hours=1),
        enabled=True,
    )
    base.update(overrides)
    return AuthorityDelegation(**base)


class TestDelegationBoundary:

    def test_delegation_cannot_escalate(self):
        """Spec §30 — 代理权限不能超过委托人的有效权限。"""
        parent = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
        )
        delegation = make_delegation(actions=("kill",))
        assert not DelegationAuthorityValidator().validate(parent, delegation)

    def test_delegation_within_parent_authority(self):
        parent = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
        )
        delegation = make_delegation(actions=("pause",))
        assert DelegationAuthorityValidator().validate(parent, delegation)

    def test_cross_resource_delegation_denied(self):
        parent = Authority(
            "commander-001", "trading", ("pause",), "ROLE"
        )
        delegation = make_delegation(resource="risk", actions=("override",))
        assert not DelegationAuthorityValidator().validate(parent, delegation)

    def test_partial_subset_allowed(self):
        parent = Authority(
            "commander-001",
            "trading",
            ("pause", "resume"),
            "ROLE",
        )
        # A 有 {pause, resume}，委托 {pause} —— Delegated ⊆ Parent。
        delegation = make_delegation(actions=("pause",))
        assert DelegationAuthorityValidator().validate(parent, delegation)


class TestEffectiveAuthorityBoundary:

    def test_role_authority_alone_does_not_execute(self):
        """Authority + Policy + Context = Effective Authority。

        Operator 有 trading:pause 权限，但 Policy 在生产环境 DENY →
        最终决策 DENY，Role 不能直接等于 Unlimited Authority。
        """
        registry = build_standard_governance()
        registry.register_principal(Principal("ops-001", "Ops One", "operator"))
        registry.register_role(Role("OPERATOR", "Operator", "Handles incidents."))
        registry.register_permission(Permission("trading:pause", "trading", "pause"))
        registry.assign_permission_to_role("OPERATOR", "trading:pause")
        registry.register_policy(
            Policy(
                policy_id="POLICY-PAUSE-BLOCKED-001",
                name="Pause Frozen",
                resource="trading",
                action="pause",
                effect="DENY",
                priority=10,
                conditions=(
                    PolicyCondition(
                        field="environment",
                        operator=ConditionOperator.EQUALS,
                        value="production",
                    ),
                ),
            )
        )
        engine = GovernanceEngine(registry)

        context = GovernanceContext(
            principal_id="ops-001",
            role_ids=("OPERATOR",),
            resource="trading",
            action="pause",
            environment="production",
        )
        decision = engine.evaluate(context)
        assert decision.effect == DecisionEffect.DENY
        assert decision.policy_id == "POLICY-PAUSE-BLOCKED-001"


class TestAuthoritySnapshot:

    def test_snapshot_records_why_approver_was_authorized(self):
        engine = GovernanceApprovalEngine(
            rules=(
                ApprovalRule(
                    rule_id="RULE-KILL-001",
                    resource="trading",
                    action="kill",
                    min_approvers=1,
                    required_roles=("INCIDENT_COMMANDER",),
                ),
            )
        )
        now = datetime.now(timezone.utc)
        approval = Approval(
            approval_id="APR-001",
            resource="trading",
            action="kill",
            requested_by="ops-001",
            requested_at=now,
            expires_at=now + timedelta(seconds=900),
            policy_id="POLICY-KILL-001",
        )
        engine.create_request(approval)
        engine.approve(
            approval,
            "commander-001",
            now,
            approver_roles=("INCIDENT_COMMANDER",),
        )

        snapshot = engine.snapshots["APR-001"]
        assert snapshot.approver_id == "commander-001"
        assert snapshot.roles == ("INCIDENT_COMMANDER",)
        assert snapshot.resource == "trading"
        assert snapshot.action == "kill"
        assert snapshot.policy_id == "POLICY-KILL-001"
        assert snapshot.source == "ROLE"
        assert snapshot.captured_at == now

    def test_snapshot_is_not_permanent_authority(self):
        """Snapshot != Current Authority：即使 snapshot 记录了角色，
        当前 authority 消失后不能据此执行。"""
        snapshot = AuthoritySnapshot(
            approval_id="APR-001",
            approver_id="commander-001",
            roles=("INCIDENT_COMMANDER",),
            resource="trading",
            action="kill",
            policy_id="POLICY-KILL-001",
        )

        # 当前 registry 中 INCIDENT_COMMANDER 并没有 trading:kill。
        registry = build_standard_governance()
        resolver = AuthorityResolver()
        authorities = resolver.resolve_from_registry(
            "commander-001",
            "trading",
            "kill",
            registry,
            role_ids=("INCIDENT_COMMANDER",),
            now=NOW,
        )

        assert snapshot.roles == ("INCIDENT_COMMANDER",)  # audit 仍可解释
        assert authorities == ()  # 但当前没有任何 authority

    def test_snapshot_never_bypasses_current_authority(self):
        registry = build_standard_governance()
        resolver = AuthorityResolver()
        # 昨天的 snapshot 说有权限，今天 role 已移除 → resolve 为空。
        snapshot = AuthoritySnapshot(
            approval_id="APR-OLD-001",
            approver_id="risk-001",
            roles=("RISK_OPERATOR",),
            resource="trading",
            action="resume",
            policy_id="POLICY-TRADING-RESUME-001",
        )
        assert snapshot is not None
        authorities = resolver.resolve_from_registry(
            "risk-001",
            "trading",
            "resume",
            registry,
            role_ids=("RISK_OPERATOR",),
            now=NOW,
        )
        # RISK_OPERATOR 无 trading:resume 权限 → 当前 authority 为空。
        assert authorities == ()
