"""
ICYQuant OPA Adapter

Adapter for Open Policy Agent (OPA) integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import logging
import json
import uuid

logger = logging.getLogger(__name__)


@dataclass
class OPAPolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    rego_package: str = "icyquant"
    rego_content: str = ""
    description: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "regoPackage": self.rego_package,
            "description": self.description,
            "enabled": self.enabled,
        }


@dataclass
class OPAQuery:
    query: str = "data.icyquant.allow"
    input_data: Dict = field(default_factory=dict)
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evaluated_at: datetime = field(default_factory=datetime.now)
    allowed: bool = False
    reason: str = ""

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "decisionId": self.decision_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


class OPAAdapter:
    """
    Adapter for Open Policy Agent (OPA) integration.

    Provides policy management and decision querying
    compatible with OPA's Rego policy language.
    """

    def __init__(self, opa_url: str = ""):
        self._opa_url = opa_url
        self._policies: Dict[str, OPAPolicy] = {}
        self._decisions: List[OPAQuery] = []
        self._max_decisions = 10000

    def create_policy(
        self,
        name: str,
        rego_content: str,
        rego_package: str = "icyquant",
        description: str = "",
    ) -> OPAPolicy:
        policy = OPAPolicy(
            name=name,
            rego_package=rego_package,
            rego_content=rego_content,
            description=description,
        )
        self._policies[name] = policy
        logger.info(f"OPA policy created: {name}")
        return policy

    def update_policy(self, name: str, rego_content: str) -> Optional[OPAPolicy]:
        policy = self._policies.get(name)
        if not policy:
            return None
        policy.rego_content = rego_content
        return policy

    def delete_policy(self, name: str):
        del self._policies[name]

    def query(
        self,
        input_data: Dict,
        query: str = "data.icyquant.allow",
    ) -> OPAQuery:
        decision = OPAQuery(
            query=query,
            input_data=input_data,
        )

        decision.allowed = self._evaluate_rego(query, input_data)
        decision.reason = "Policy evaluation complete"

        self._decisions.append(decision)
        if len(self._decisions) > self._max_decisions:
            self._decisions = self._decisions[-self._max_decisions:]

        return decision

    def _evaluate_rego(self, query: str, input_data: Dict) -> bool:
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if self._match_policy(policy, input_data):
                return True
        return False

    def _match_policy(self, policy: OPAPolicy, input_data: Dict) -> bool:
        if "allow" in policy.rego_content.lower():
            return self._check_allow_rules(policy.rego_content, input_data)
        return False

    def _check_allow_rules(self, rego: str, input_data: Dict) -> bool:
        lines = rego.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("input."):
                parts = line.split("==")
                if len(parts) == 2:
                    attr_path = parts[0].strip().replace("input.", "")
                    expected = parts[1].strip().strip('"').strip("'")
                    actual = self._resolve_input(attr_path, input_data)
                    if str(actual) != expected:
                        return False
        return True

    def _resolve_input(self, path: str, input_data: Dict) -> Optional[str]:
        parts = path.split(".")
        value = input_data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return str(value) if value is not None else None

    def list_policies(self) -> List[Dict]:
        return [p.to_dict() for p in self._policies.values()]

    def get_decisions(self, limit: int = 100) -> List[Dict]:
        return [d.to_dict() for d in self._decisions[-limit:]]

    def health_check(self) -> Dict:
        return {
            "opaUrl": self._opa_url or "local",
            "policiesCount": len(self._policies),
            "decisionsCount": len(self._decisions),
            "timestamp": datetime.now().isoformat(),
        }

    def to_dict(self) -> Dict:
        return {
            "opaUrl": self._opa_url or "local",
            "totalPolicies": len(self._policies),
            "totalDecisions": len(self._decisions),
        }
