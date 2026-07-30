"""
ICYQuant Policy Engine

Open Policy Agent (OPA) compatible policy evaluation engine.
All requests must pass through policy checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging
import uuid
import json
import re

logger = logging.getLogger(__name__)


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class PolicyCondition:
    attribute: str
    operator: str
    value: Any

    def evaluate(self, context: Dict) -> bool:
        actual = self._resolve(self.attribute, context)
        operators = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: self._cmp(a, b, lambda x, y: x > y),
            "lt": lambda a, b: self._cmp(a, b, lambda x, y: x < y),
            "ge": lambda a, b: self._cmp(a, b, lambda x, y: x >= y),
            "le": lambda a, b: self._cmp(a, b, lambda x, y: x <= y),
            "in": lambda a, b: a in b if isinstance(b, (list, set)) else False,
            "contains": lambda a, b: b in str(a) if a else False,
            "regex": lambda a, b: bool(re.search(b, str(a))) if a else False,
            "exists": lambda a, b: a is not None,
            "not_exists": lambda a, b: a is None,
        }
        op_fn = operators.get(self.operator)
        if not op_fn:
            return False
        return op_fn(actual, self.value)

    @staticmethod
    def _resolve(attribute: str, context: Dict) -> Any:
        parts = attribute.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    @staticmethod
    def _cmp(a, b, op):
        try:
            return op(float(a), float(b))
        except (TypeError, ValueError):
            return op(a, b)

    def to_dict(self) -> Dict:
        return {
            "attribute": self.attribute,
            "operator": self.operator,
            "value": self.value,
        }


@dataclass
class PolicyStatement:
    effect: PolicyEffect = PolicyEffect.DENY
    conditions: List[PolicyCondition] = field(default_factory=list)
    description: str = ""

    def evaluate(self, context: Dict) -> Optional[bool]:
        if not self.conditions:
            return self.effect == PolicyEffect.ALLOW
        results = [c.evaluate(context) for c in self.conditions]
        if self.effect == PolicyEffect.ALLOW:
            return all(results)
        return all(results)

    def to_dict(self) -> Dict:
        return {
            "effect": self.effect.value,
            "conditions": [c.to_dict() for c in self.conditions],
            "description": self.description,
        }


@dataclass
class Policy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = True
    priority: int = 0
    statements: List[PolicyStatement] = field(default_factory=list)
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    labels: Dict[str, str] = field(default_factory=dict)

    def evaluate(self, context: Dict) -> Optional[PolicyEffect]:
        if not self.enabled:
            return None
        for statement in self.statements:
            result = statement.evaluate(context)
            if result is True:
                return statement.effect
        return None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority,
            "statements": [s.to_dict() for s in self.statements],
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "version": self.version,
        }


@dataclass
class PolicyDecision:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: PolicyEffect = PolicyEffect.DENY
    matched_policy: Optional[str] = None
    reason: str = ""
    evaluated_at: datetime = field(default_factory=datetime.now)
    context_snapshot: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "requestId": self.request_id,
            "decision": self.decision.value,
            "matchedPolicy": self.matched_policy,
            "reason": self.reason,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


class PolicyEngine:
    """
    OPA-compatible policy evaluation engine.

    Evaluates requests against a set of policies with configurable
    priority, conditions, and effects. Default deny behavior.
    """

    def __init__(self):
        self._policies: Dict[str, Policy] = {}
        self._decision_log: List[PolicyDecision] = []
        self._max_log_size = 50000
        self._default_decision = PolicyEffect.DENY
        self._custom_evaluators: Dict[str, Callable] = {}

    def create_policy(self, policy: Policy) -> Policy:
        if policy.name in self._policies:
            raise ValueError(f"Policy '{policy.name}' already exists")
        self._policies[policy.name] = policy
        logger.info(f"Policy created: {policy.name}")
        return policy

    def update_policy(self, name: str, **kwargs) -> Optional[Policy]:
        policy = self._policies.get(name)
        if not policy:
            return None
        for key, value in kwargs.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        policy.updated_at = datetime.now()
        return policy

    def delete_policy(self, name: str):
        policy = self._policies.get(name)
        if not policy:
            raise ValueError(f"Policy '{name}' not found")
        del self._policies[name]

    def evaluate(
        self,
        context: Dict,
        request_id: Optional[str] = None,
    ) -> PolicyDecision:
        sorted_policies = sorted(
            self._policies.values(),
            key=lambda p: p.priority,
            reverse=True,
        )

        for policy in sorted_policies:
            result = policy.evaluate(context)
            if result is not None:
                decision = PolicyDecision(
                    request_id=request_id or str(uuid.uuid4())[:12],
                    decision=result,
                    matched_policy=policy.name,
                    reason=f"Policy '{policy.name}' matched",
                    context_snapshot=context,
                )
                self._log_decision(decision)
                return decision

        decision = PolicyDecision(
            request_id=request_id or str(uuid.uuid4())[:12],
            decision=self._default_decision,
            reason="No policy matched, default deny",
            context_snapshot=context,
        )
        self._log_decision(decision)
        return decision

    def register_evaluator(self, name: str, evaluator: Callable):
        self._custom_evaluators[name] = evaluator

    def list_policies(self) -> List[Dict]:
        return [p.to_dict() for p in self._policies.values()]

    def get_policy(self, name: str) -> Optional[Policy]:
        return self._policies.get(name)

    def get_decision_log(self, limit: int = 100) -> List[Dict]:
        return [d.to_dict() for d in self._decision_log[-limit:]]

    def _log_decision(self, decision: PolicyDecision):
        self._decision_log.append(decision)
        if len(self._decision_log) > self._max_log_size:
            self._decision_log = self._decision_log[-self._max_log_size:]

    def to_dict(self) -> Dict:
        return {
            "totalPolicies": len(self._policies),
            "activePolicies": sum(1 for p in self._policies.values() if p.enabled),
            "totalDecisions": len(self._decision_log),
        }
