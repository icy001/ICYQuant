"""Anti-Affinity Rules — prevent jobs from landing on the same node/rack/zone.

Anti-affinity improves fault tolerance by spreading related workloads
across different failure domains.  For example, two replicas of the same
risk engine should never run on the same physical machine.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class AntiAffinityScope(str, enum.Enum):
    NODE = "node"     # Avoid same node
    RACK = "rack"     # Avoid same rack
    ZONE = "zone"     # Avoid same availability zone
    REGION = "region" # Avoid same region


@dataclass
class AntiAffinityRule:
    """A rule that prevents co-location of jobs.

    Usage::

        rule = AntiAffinityRule(
            name="risk-engine-ha",
            scope=AntiAffinityScope.NODE,
            source_jobs={"job-risk-1", "job-risk-2"},
        )
    """

    rule_id: str = ""
    name: str = ""
    scope: AntiAffinityScope = AntiAffinityScope.NODE
    source_jobs: Set[str] = field(default_factory=set)
    source_labels: Dict[str, str] = field(default_factory=dict)
    excluded_nodes: List[str] = field(default_factory=list)
    enabled: bool = True

    def matches(self, job_id: str, labels: Optional[Dict[str, str]] = None) -> bool:
        if not self.enabled:
            return False
        if self.source_jobs and job_id in self.source_jobs:
            return True
        if self.source_labels and labels:
            for k, v in self.source_labels.items():
                if labels.get(k) == v:
                    return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id, "name": self.name,
            "scope": self.scope.value,
            "source_jobs": list(self.source_jobs),
            "excluded_nodes": self.excluded_nodes,
            "enabled": self.enabled,
        }


class AntiAffinityManager:
    """Manages anti-affinity rules for the scheduler.

    Usage::

        mgr = AntiAffinityManager()
        mgr.add_rule(AntiAffinityRule(...))
        excluded = mgr.get_excluded_nodes("job-risk-1")
    """

    def __init__(self) -> None:
        self._rules: List[AntiAffinityRule] = []

    def add_rule(self, rule: AntiAffinityRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def get_excluded_nodes(
        self, job_id: str, labels: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Return nodes that must be excluded for this job."""
        excluded: List[str] = []
        for rule in self._rules:
            if rule.matches(job_id, labels):
                excluded.extend(rule.excluded_nodes)
        return list(set(excluded))

    def get_scope_for_job(
        self, job_id: str, labels: Optional[Dict[str, str]] = None,
    ) -> Optional[AntiAffinityScope]:
        """Return the strictest anti-affinity scope for a job."""
        scopes = {
            r.scope for r in self._rules
            if r.matches(job_id, labels)
        }
        if not scopes:
            return None
        # Prioritize: NODE > RACK > ZONE > REGION
        for scope in AntiAffinityScope:
            if scope in scopes:
                return scope
        return None

    def list_rules(self) -> List[AntiAffinityRule]:
        return list(self._rules)

    def health_report(self) -> Dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "enabled": sum(1 for r in self._rules if r.enabled),
        }
