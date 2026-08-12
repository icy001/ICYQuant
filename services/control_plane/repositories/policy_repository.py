"""
PolicyRepository — persistence for policies and their evaluation audit trail.

Two stores:

    1. policies      — registered Policy documents (policy_id → policy dict)
    2. evaluations   — append-only audit log of PolicyEvaluations

The evaluation log is the replay source: given the same context snapshot and
policy versions, the engine must reproduce the same decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..policy.policy import Policy
from ..policy.policy_engine import PolicyEvaluation


@dataclass
class PolicyRepository:
    """In-memory repository for the Policy Engine."""

    _policies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _evaluations: List[Dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # policies
    # ------------------------------------------------------------------

    def save_policy(self, policy: Policy) -> None:
        """Upsert a policy by its stable ``policy_id``."""
        self._policies[policy.policy_id] = policy.to_dict()

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        data = self._policies.get(policy_id)
        return Policy.from_dict(data) if data is not None else None

    def list_policies(self) -> List[Policy]:
        return [Policy.from_dict(d) for d in self._policies.values()]

    def policy_count(self) -> int:
        return len(self._policies)

    def get_policy_version(self, policy_id: str) -> Optional[str]:
        data = self._policies.get(policy_id)
        return data["policy_version"] if data else None

    def delete_policy(self, policy_id: str) -> bool:
        return self._policies.pop(policy_id, None) is not None

    def clear_policies(self) -> None:
        self._policies.clear()

    # ------------------------------------------------------------------
    # evaluation audit log
    # ------------------------------------------------------------------

    def record_evaluation(self, evaluation: PolicyEvaluation) -> str:
        """Append an evaluation to the audit log; returns its id."""
        payload = evaluation.to_dict()
        payload["record_id"] = f"PE-{len(self._evaluations) + 1:05d}"
        self._evaluations.append(payload)
        return payload["record_id"]

    def get_evaluations(
        self, offset: int = 0, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        items = self._evaluations[offset:]
        if limit is not None:
            items = items[:limit]
        return items

    def evaluation_count(self) -> int:
        return len(self._evaluations)

    def get_evaluation(self, record_id: str) -> Optional[Dict[str, Any]]:
        for payload in self._evaluations:
            if payload.get("record_id") == record_id:
                return payload
        return None

    def clear_evaluations(self) -> None:
        self._evaluations.clear()

    # ------------------------------------------------------------------
    # snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Serialise the whole repository state (for backup / debugging)."""
        return {
            "policies": list(self._policies.values()),
            "evaluations": list(self._evaluations),
        }

    def restore(self, data: Dict[str, Any]) -> None:
        """Restore repository state from ``snapshot()`` output."""
        self._policies = {
            item["policy_id"]: item for item in data.get("policies", [])
        }
        self._evaluations = list(data.get("evaluations", []))
