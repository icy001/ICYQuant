"""
ICYQuant Zero Trust Security Engine

Default DENY. Every request must be explicitly authenticated, authorized,
and policy-evaluated before access is granted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class TrustDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"
    REVIEW = "review"


@dataclass
class SecurityContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    service: str = ""
    action: str = ""
    resource: str = ""
    ip_address: str = ""
    user_agent: str = ""
    mfa_verified: bool = False
    token_present: bool = False
    roles: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "requestId": self.request_id,
            "userId": self.user_id,
            "service": self.service,
            "action": self.action,
            "resource": self.resource,
            "ipAddress": self.ip_address,
            "mfaVerified": self.mfa_verified,
            "tokenPresent": self.token_present,
            "roles": self.roles,
            "attributes": self.attributes,
        }


@dataclass
class RequestEvaluation:
    request_id: str = ""
    decision: TrustDecision = TrustDecision.DENY
    reason: str = ""
    checks_performed: List[str] = field(default_factory=list)
    policy_matched: Optional[str] = None
    evaluated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "requestId": self.request_id,
            "decision": self.decision.value,
            "reason": self.reason,
            "checksPerformed": self.checks_performed,
            "policyMatched": self.policy_matched,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


@dataclass
class ZeroTrustPolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = True
    priority: int = 0
    conditions: Dict[str, str] = field(default_factory=dict)
    effect: TrustDecision = TrustDecision.DENY
    services: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority,
            "conditions": self.conditions,
            "effect": self.effect.value,
            "services": self.services,
            "actions": self.actions,
        }


class ZeroTrustEngine:
    """
    Zero Trust security engine.

    Default DENY. Evaluates every request against identity, authentication,
    authorization, and policy checks before granting access.
    """

    def __init__(self):
        self._policies: List[ZeroTrustPolicy] = []
        self._default_decision = TrustDecision.DENY
        self._evaluation_log: List[RequestEvaluation] = []
        self._max_log_size = 10000

    def add_policy(self, policy: ZeroTrustPolicy):
        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority, reverse=True)

    def remove_policy(self, policy_id: str):
        self._policies = [p for p in self._policies if p.id != policy_id]

    def evaluate(self, context: SecurityContext) -> RequestEvaluation:
        checks: List[str] = []

        if not context.token_present:
            evaluation = RequestEvaluation(
                request_id=context.request_id,
                decision=TrustDecision.DENY,
                reason="No authentication token presented",
                checks_performed=["token_presence"],
            )
            self._log_evaluation(evaluation)
            return evaluation
        checks.append("token_presence")

        if not context.user_id:
            evaluation = RequestEvaluation(
                request_id=context.request_id,
                decision=TrustDecision.DENY,
                reason="No authenticated user",
                checks_performed=checks,
            )
            self._log_evaluation(evaluation)
            return evaluation
        checks.append("user_identity")

        if context.mfa_verified:
            checks.append("mfa_verification")

        for policy in self._policies:
            if not policy.enabled:
                continue
            if self._policy_matches(policy, context):
                evaluation = RequestEvaluation(
                    request_id=context.request_id,
                    decision=policy.effect,
                    reason=f"Policy '{policy.name}' matched",
                    checks_performed=checks + ["policy_match"],
                    policy_matched=policy.name,
                )
                self._log_evaluation(evaluation)
                return evaluation

        evaluation = RequestEvaluation(
            request_id=context.request_id,
            decision=self._default_decision,
            reason="No policy matched, default deny",
            checks_performed=checks + ["default_policy"],
        )
        self._log_evaluation(evaluation)
        return evaluation

    def _policy_matches(self, policy: ZeroTrustPolicy, context: SecurityContext) -> bool:
        if policy.services and context.service not in policy.services:
            return False
        if policy.actions and context.action not in policy.actions:
            return False
        for attr_key, expected in policy.conditions.items():
            actual = context.attributes.get(attr_key, "")
            if actual != expected:
                return False
        return True

    def _log_evaluation(self, evaluation: RequestEvaluation):
        self._evaluation_log.append(evaluation)
        if len(self._evaluation_log) > self._max_log_size:
            self._evaluation_log = self._evaluation_log[-self._max_log_size:]

    def get_evaluation_log(self, limit: int = 100) -> List[RequestEvaluation]:
        return self._evaluation_log[-limit:]

    def list_policies(self) -> List[Dict]:
        return [p.to_dict() for p in self._policies]

    def to_dict(self) -> Dict:
        return {
            "policies": self.list_policies(),
            "defaultDecision": self._default_decision.value,
            "totalEvaluations": len(self._evaluation_log),
        }
