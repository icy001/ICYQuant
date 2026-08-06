"""Affinity Rules — prefer placing jobs on specific nodes or near related workloads.

Affinity rules steer the scheduler toward nodes that share data, belong
to the same workflow, or reside in the same failure domain.  This reduces
cross-node communication and improves cache locality.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class AffinityType(str, enum.Enum):
    WORKFLOW = "workflow"       # Same workflow jobs together
    DATA = "data"               # Data-local placement
    GPU = "gpu"                 # GPU-aware placement
    REGION = "region"           # Same region/zone
    CUSTOM = "custom"           # Arbitrary label-based


@dataclass
class AffinityRule:
    """A rule that steers placement toward preferred nodes.

    Usage::

        rule = AffinityRule(
            rule_type=AffinityType.WORKFLOW,
            source_job="workflow-risk",
            target_nodes=["node-1", "node-2"],
            weight=0.8,
        )
    """

    rule_id: str = ""
    name: str = ""
    rule_type: AffinityType = AffinityType.CUSTOM
    source_jobs: Set[str] = field(default_factory=set)
    source_labels: Dict[str, str] = field(default_factory=dict)
    target_nodes: List[str] = field(default_factory=list)
    target_labels: Dict[str, str] = field(default_factory=dict)
    weight: float = 0.5  # 0.0–1.0, how strongly to prefer
    enabled: bool = True

    def matches(self, job_id: str, labels: Optional[Dict[str, str]] = None) -> bool:
        """Check if this rule applies to the given job."""
        if not self.enabled:
            return False
        if self.source_jobs and job_id in self.source_jobs:
            return True
        if self.source_labels and labels:
            for k, v in self.source_labels.items():
                if labels.get(k) == v:
                    return True
        return len(self.source_jobs) == 0 and len(self.source_labels) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id, "name": self.name,
            "rule_type": self.rule_type.value,
            "source_jobs": list(self.source_jobs),
            "target_nodes": self.target_nodes,
            "weight": self.weight, "enabled": self.enabled,
        }


class AffinityManager:
    """Manages a set of affinity rules.

    Usage::

        mgr = AffinityManager()
        mgr.add_rule(AffinityRule(...))
        nodes = mgr.get_preferred_nodes("job-1", {"workflow": "risk"})
    """

    def __init__(self) -> None:
        self._rules: List[AffinityRule] = []

    def add_rule(self, rule: AffinityRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def get_preferred_nodes(
        self, job_id: str, labels: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Return the union of all preferred nodes from matching rules."""
        nodes: List[str] = []
        for rule in self._rules:
            if rule.matches(job_id, labels):
                nodes.extend(rule.target_nodes)
        return list(set(nodes))

    def list_rules(self) -> List[AffinityRule]:
        return list(self._rules)

    def health_report(self) -> Dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "enabled": sum(1 for r in self._rules if r.enabled),
        }
