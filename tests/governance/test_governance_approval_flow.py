"""End-to-end approval authority chain (Commit 28 Part 1.4).

    Principal
      ├── Role Authority
      └── Delegated Authority
              ▼
        Authority Resolver
              ▼
          Policy Engine
              ▼
       REQUIRE_APPROVAL
              ▼
          Approval Rule
              ▼
             Quorum
              ▼
          APPROVED
              ▼
       Governance Re-Eval
              ▼
            ALLOW
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.approval import (
    Approval,
    ApprovalDecision,
    ApprovalState,
)
from services.governance.approval_engine import GovernanceApprovalEngine
from services.governance.approval_rule import ApprovalRule
from services.governance.authority import AuthorityResolver
from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceEngine,
)
from services.governance.delegation import AuthorityDelegation
from services.governance.models import Principal
from services.governance.policy import Policy
from services.governance.quorum import QuorumEvaluator, QuorumRule
from services.governance.registry import build_standard_governance


def make_registry():
    """Standard governance + admins + governance self-protection policy."""
    registry = build_standard_governance()
    registry.register_principal(Principal("admin-001", "Admin One", "admin"))
    registry.register_principal(Principal("admin-002", "Admin Two", "admin"))
    registry.register_principal(Principal("admin-003", "Admin Three", "admin"))
    registry.register_principal(Principal("ops-001", "Ops One", "operator"))
    registry.register_principal(Principal("control-001", "Control", "operator"))
    # Governance 保护 Governance：policy:update 本身必须双管理员批准。
    registry.register_policy(
        Policy(
            policy_id="POLICY-GOVERNANCE-POLICY-UPDATE-001",
            name="Governance Policy Change",
            resource="policy",
            action="update",
            effect="REQUIRE_APPROVAL",
            priority=50,
            required_roles=("ADMINISTRATOR",),
            requires_approval=True,
        )
    )
    return registry


def policy_update_context(principal_id, approval_id=None):
    return GovernanceContext(
        principal_id=principal_id,
        role_ids=("ADMINISTRATOR",),
        resource="policy",
        action="update",
        environment="production",
        approval_id=approval_id,
    )


def resume_context(principal_id="control-001", approval_id="APR-RESUME-001"):
    return GovernanceContext(
        principal_id=principal_id,
        role_ids=("CONTROL_OPERATOR",),
        resource="trading",
        action="resume",
        environment="production",
        incident_id="INC-001",
        severity="CRITICAL",
        approval_id=approval_id,
        recovery_status="READY",
        reconciliation_status="PASSED",
        risk_status="PASSED",
    )


def make_policy_engine():
    return GovernanceApprovalEngine(
        rules=(
            ApprovalRule(
                rule_id="RULE-POLICY-UPDATE-001",
                resource="policy",
                action="update",
                min_approvers=2,
                required_roles=("ADMINISTRATOR",),
                approval_timeout_seconds=900,
            ),
        )
    )


def make_policy_approval(now, requested_by="admin-001"):
    return Approval(
        approval_id="APR-POLICY-001",
        resource="policy",
        action="update",
        requested_by=requested_by,
        requested_at=now,
        expires_at=now + timedelta(seconds=900),
        policy_id="POLICY-GOVERNANCE-POLICY-UPDATE-001",
    )


def make_kill_engine(delegations=()):
    return GovernanceApprovalEngine(
        rules=(
            ApprovalRule(
                rule_id="RULE-KILL-001",
                resource="trading",
                action="kill",
                min_approvers=2,
                required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR"),
                approval_timeout_seconds=900,
            ),
        ),
        authority_resolver=AuthorityResolver(delegations=delegations),
    )


def make_kill_approval(now, requested_by="ops-001"):
    return Approval(
        approval_id="APR-KILL-001",
        resource="trading",
        action="kill",
        requested_by=requested_by,
        requested_at=now,
        expires_at=now + timedelta(seconds=900),
        policy_id="POLICY-TRADING-KILL-001",
    )


def decision_from(approved_approval, approver_id, reason="approve"):
    return ApprovalDecision(
        approval_id=approved_approval.approval_id,
        approver_id=approver_id,
        approved=True,
        timestamp=approved_approval.approved_at,
        reason=reason,
    )


class TestGovernanceSelfProtection:

    def test_policy_change_requires_separation(self):
        """Spec §33 — policy:update 不能由普通 Operator 执行。"""
        registry = make_registry()
        governance = GovernanceEngine(registry=registry)

        decision = governance.evaluate(policy_update_context("admin-001"))

        assert decision.effect == DecisionEffect.REQUIRE_APPROVAL
        assert decision.approval_required is True

    def test_admin_cannot_self_approve_policy_change(self):
        """Admin A 不能修改 Policy 后自己批准（Requester != Approver）。"""
        engine = make_policy_engine()
        now = datetime.now(timezone.utc)

        approval = make_policy_approval(now, requested_by="admin-001")
        engine.create_request(approval)

        with pytest.raises(PermissionError):
            engine.approve(
                approval, "admin-001", now, approver_roles=("ADMINISTRATOR",)
            )

    def test_two_admins_satisfy_policy_change_quorum(self):
        """policy:update 需要 ADMIN + SECOND ADMIN（2 个不同 Administrator）。"""
        engine = make_policy_engine()
        now = datetime.now(timezone.utc)

        approval = make_policy_approval(now)
        engine.create_request(approval)

        first = engine.approve(
            approval, "admin-002", now, approver_roles=("ADMINISTRATOR",)
        )
        second = engine.approve(
            approval,
            "admin-003",
            now + timedelta(seconds=1),
            approver_roles=("ADMINISTRATOR",),
        )
        assert first.state == ApprovalState.APPROVED
        assert second.state == ApprovalState.APPROVED

        rule = QuorumRule(
            minimum=2,
            distinct_principals=True,
            required_roles=("ADMINISTRATOR",),
        )
        decisions = [
            decision_from(first, "admin-002"),
            decision_from(second, "admin-003"),
        ]
        roles = {
            "admin-002": ("ADMINISTRATOR",),
            "admin-003": ("ADMINISTRATOR",),
        }
        assert QuorumEvaluator().evaluate(decisions, roles, rule)

    def test_same_admin_twice_does_not_satisfy_quorum(self):
        engine = make_policy_engine()
        now = datetime.now(timezone.utc)

        approval = make_policy_approval(now)
        engine.create_request(approval)

        first = engine.approve(
            approval, "admin-002", now, approver_roles=("ADMINISTRATOR",)
        )
        rule = QuorumRule(
            minimum=2,
            distinct_principals=True,
            required_roles=("ADMINISTRATOR",),
        )
        decisions = [
            decision_from(first, "admin-002"),
            decision_from(first, "admin-002"),  # 重复批准者只算 1 人
        ]
        roles = {"admin-002": ("ADMINISTRATOR",)}
        assert not QuorumEvaluator().evaluate(decisions, roles, rule)

    def test_policy_change_approval_does_not_bypass_governance(self):
        """审批通过后仍要 re-evaluate：policy:update 始终 REQUIRE_APPROVAL，
        旧的 Approval 不能让它变成 ALLOW（Approval 不绕过 Governance）。"""
        registry = make_registry()
        governance = GovernanceEngine(registry=registry)
        engine = make_policy_engine()
        now = datetime.now(timezone.utc)

        approval = make_policy_approval(now)
        engine.create_request(approval)
        approved = engine.approve(
            approval, "admin-002", now, approver_roles=("ADMINISTRATOR",)
        )
        engine.approve(
            approval,
            "admin-003",
            now + timedelta(seconds=1),
            approver_roles=("ADMINISTRATOR",),
        )
        assert approved.state == ApprovalState.APPROVED

        # 当前 Governance 仍然要求审批 → 不能执行、不消费。
        decision = governance.evaluate(
            policy_update_context("admin-001", approval_id="APR-POLICY-001")
        )
        assert decision.effect == DecisionEffect.REQUIRE_APPROVAL

        # authorize_execution 只放行 ALLOW：非 ALLOW 原样返回 → 执行被阻止。
        final = engine.authorize_execution(approved, decision, now)
        assert final.effect == DecisionEffect.REQUIRE_APPROVAL
        assert engine.current_state("APR-POLICY-001") == ApprovalState.APPROVED


class TestFullApprovalAuthorityChain:

    def test_full_chain_role_authority(self):
        """完整链路：Role Authority → Policy → REQUIRE_APPROVAL → Approval →
        Quorum → Re-Eval ALLOW → CONSUMED。"""
        registry = make_registry()
        governance = GovernanceEngine(registry=registry)
        resolver = AuthorityResolver()
        now = datetime.now(timezone.utc)

        # 1) Role Authority：control-001 有 trading:resume。
        authorities = resolver.resolve_from_registry(
            "control-001",
            "trading",
            "resume",
            registry,
            role_ids=("CONTROL_OPERATOR",),
            now=now,
        )
        assert any(a.source == "ROLE" for a in authorities)

        # 2) 无 Approval → approval_id EXISTS 不满足 → DENY。
        denied = governance.evaluate(resume_context(approval_id=None))
        assert denied.effect == DecisionEffect.DENY

        # 3) 批准 → Re-Eval ALLOW。
        engine = GovernanceApprovalEngine(
            rules=(
                ApprovalRule(
                    rule_id="RULE-RESUME-001",
                    resource="trading",
                    action="resume",
                    min_approvers=1,
                    required_roles=("CONTROL_OPERATOR",),
                ),
            )
        )
        approval = Approval(
            approval_id="APR-RESUME-001",
            resource="trading",
            action="resume",
            requested_by="ops-001",
            requested_at=now,
            expires_at=now + timedelta(seconds=900),
            policy_id="POLICY-TRADING-RESUME-001",
        )
        engine.create_request(approval)
        approved = engine.approve(
            approval, "control-001", now, approver_roles=("CONTROL_OPERATOR",)
        )
        assert approved.state == ApprovalState.APPROVED

        decision = governance.evaluate(resume_context())
        assert decision.effect == DecisionEffect.ALLOW

        # 4) Quorum 满足。
        rule = QuorumRule(minimum=1, required_roles=("CONTROL_OPERATOR",))
        assert QuorumEvaluator().evaluate(
            [decision_from(approved, "control-001")],
            {"control-001": ("CONTROL_OPERATOR",)},
            rule,
        )

        # 5) 执行（Governance Re-Evaluation 通过后消费）。
        final = engine.authorize_execution(approved, decision, now)
        assert final.effect == DecisionEffect.ALLOW
        assert engine.current_state("APR-RESUME-001") == ApprovalState.CONSUMED


class TestDelegationInApprovalFlow:

    def test_delegated_authority_stands_in_for_offline_commander(self):
        """02:00 重大事故，Incident Commander OFFLINE —— 委托给 commander-002。"""
        now = datetime.now(timezone.utc)
        delegation = AuthorityDelegation(
            delegation_id="DEL-EMERGENCY-001",
            delegator_id="commander-001",
            delegate_id="commander-002",
            resource="trading",
            actions=("kill",),
            valid_from=now - timedelta(minutes=5),
            valid_until=now + timedelta(minutes=25),
        )
        engine = make_kill_engine(delegations=(delegation,))
        approval = make_kill_approval(now)
        engine.create_request(approval)

        # commander-002 没有 INCIDENT_COMMANDER 角色，但持有有效委托 → 可以批准。
        approved = engine.approve(
            approval, "commander-002", now, approver_roles=()
        )
        assert approved.state == ApprovalState.APPROVED

        snapshot = engine.snapshots["APR-KILL-001"]
        assert snapshot.source == "DELEGATION"
        assert snapshot.source_id == "DEL-EMERGENCY-001"

    def test_delegate_without_delegation_cannot_approve(self):
        now = datetime.now(timezone.utc)
        engine = make_kill_engine()  # 没有任何委托
        approval = make_kill_approval(now)
        engine.create_request(approval)

        with pytest.raises(PermissionError):
            engine.approve(approval, "commander-002", now, approver_roles=())

    def test_expired_delegation_blocks_approval(self):
        now = datetime.now(timezone.utc)
        delegation = AuthorityDelegation(
            delegation_id="DEL-EXPIRED-001",
            delegator_id="commander-001",
            delegate_id="commander-002",
            resource="trading",
            actions=("kill",),
            valid_from=now - timedelta(minutes=30),
            valid_until=now - timedelta(minutes=5),  # 已过期
        )
        engine = make_kill_engine(delegations=(delegation,))
        approval = make_kill_approval(now)
        engine.create_request(approval)

        with pytest.raises(PermissionError):
            engine.approve(approval, "commander-002", now, approver_roles=())

    def test_delegation_enables_split_quorum_approval(self):
        """Commander（委托）+ Risk（角色）→ split quorum 满足。"""
        now = datetime.now(timezone.utc)
        delegation = AuthorityDelegation(
            delegation_id="DEL-EMERGENCY-002",
            delegator_id="commander-001",
            delegate_id="commander-002",
            resource="trading",
            actions=("kill",),
            valid_from=now - timedelta(minutes=5),
            valid_until=now + timedelta(minutes=25),
        )
        engine = make_kill_engine(delegations=(delegation,))
        approval = make_kill_approval(now)
        engine.create_request(approval)

        first = engine.approve(approval, "commander-002", now, approver_roles=())
        second = engine.approve(
            approval,
            "risk-001",
            now + timedelta(seconds=1),
            approver_roles=("RISK_OPERATOR",),
        )
        assert first.state == ApprovalState.APPROVED
        assert second.state == ApprovalState.APPROVED

        rule = QuorumRule(
            minimum=2,
            distinct_principals=True,
            required_roles=("INCIDENT_COMMANDER", "RISK_OPERATOR"),
            distinct_roles=True,
        )
        decisions = [
            decision_from(first, "commander-002"),
            decision_from(second, "risk-001"),
        ]
        roles = {
            "commander-002": ("INCIDENT_COMMANDER",),  # 代行 Commander 职责
            "risk-001": ("RISK_OPERATOR",),
        }
        assert QuorumEvaluator().evaluate(decisions, roles, rule)
