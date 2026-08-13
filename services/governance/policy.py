"""
Policy — institutional policy definition.

For versioned policies, see: policy_version.py which provides full
lifecycle management (DRAFT→ACTIVE→ARCHIVED), content hashing,
and immutable version snapshots.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .policy_rule import PolicyRule
from .policy_condition import PolicyCondition


class PolicyScope:
    """Standard governance scopes (also available in PolicyScopeConstants)."""

    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    PORTFOLIO = "PORTFOLIO"
    STRATEGY = "STRATEGY"
    ASSET = "ASSET"
    FACTOR = "FACTOR"
    ORDER = "ORDER"
    EXECUTION = "EXECUTION"
    CAPITAL = "CAPITAL"
    RISK = "RISK"

    # Market scope (added per policy_scope.py)
    MARKET = "MARKET"


@dataclass
class InstitutionalPolicy:
    """An institutional policy consisting of multiple rules."""

    policy_id: str = field(default_factory=lambda: f"POL-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    scope: str = PolicyScope.GLOBAL
    enabled: bool = True

    # Rules
    rules: List[PolicyRule] = field(default_factory=list)

    # Meta
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "SYSTEM"

    def applies_to_decision_type(self, decision_type: str) -> bool:
        """Check if this policy applies to a given decision type."""
        for rule in self.rules:
            if rule.applies_to_decision_type(decision_type):
                return True
        return False

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)
        self.updated_at = time.time()

    def remove_rule(self, rule_id: str) -> None:
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        self.updated_at = time.time()

    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "enabled": self.enabled,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstitutionalPolicy":
        policy = cls(
            policy_id=data.get("policy_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            scope=data.get("scope", PolicyScope.GLOBAL),
            enabled=data.get("enabled", True),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        for rd in data.get("rules", []):
            policy.add_rule(PolicyRule.from_dict(rd))
        return policy


# ---------------------------------------------------------------------------
# Commit 28 Part 1.1 — Production Governance Layer
#
# 注意：上方 InstitutionalPolicy 是 Commit 20 的规则型机构策略（scope + rules）。
# 下方的 Policy 是 Commit 28 的权限型生产治理策略（resource + action）。
# 两者同名不同义：
#   Permission 回答"你有没有资格申请？"
#   Policy 回答"现在能不能执行？"
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Policy:
    """Production governance policy (Commit 28 Part 1.1).

    A permission-style policy binding a resource+action to a priority.
    Conditions / severity / approval evaluation is added by the next
    commit part (Policy Evaluation Engine).
    """

    policy_id: str
    name: str
    resource: str
    action: str
    enabled: bool = True
    priority: int = 100
