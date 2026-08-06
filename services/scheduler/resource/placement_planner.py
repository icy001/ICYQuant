"""Placement Planner — generates and executes placement plans.

The :class:`PlacementPlanner` is the decision engine that takes a job,
estimates its resource needs, scores candidate nodes, applies affinity/
anti-affinity rules, and produces a :class:`PlacementPlan` for execution.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .node_inventory import NodeInventory, NodeRecord
from .node_selector import NodeSelector, SelectionStrategy
from .resource_estimator import ResourceEstimator, EstimateResult
from .affinity import AffinityRule
from .anti_affinity import AntiAffinityRule
from .topology import TopologyManager, TopologyDomain

logger = logging.getLogger(__name__)


@dataclass
class PlacementPlan:
    """A plan for placing one or more jobs onto nodes."""

    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    assignments: List[PlacementAssignment] = field(default_factory=list)
    status: str = "pending"

    @property
    def node_count(self) -> int:
        return len(set(a.node_id for a in self.assignments))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id, "status": self.status,
            "assignments": [a.to_dict() for a in self.assignments],
        }


@dataclass
class PlacementAssignment:
    """A single job→node assignment within a plan."""

    job_id: str
    node_id: str
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    gpu_units: float = 0.0
    score: float = 0.0
    reason: str = ""


class PlacementPlanner:
    """Generates intelligent placement plans for jobs.

    Pipeline: estimate → filter → score → apply rules → assign

    Usage::

        planner = PlacementPlanner(inventory, estimator, topology)
        plan = await planner.plan(job_id="job-1", cpu=4, memory_mb=8192)
        # plan.assignments[0].node_id → "node-3"
    """

    def __init__(
        self, inventory: NodeInventory,
        estimator: ResourceEstimator,
        topology: Optional[TopologyManager] = None,
    ) -> None:
        self._inventory = inventory
        self._estimator = estimator
        self._topology = topology
        self._selector = NodeSelector(inventory)

        self._affinity_rules: List[AffinityRule] = []
        self._anti_affinity_rules: List[AntiAffinityRule] = []

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    async def plan(
        self, job_id: str, cpu_cores: float = 0.0, memory_mb: float = 0.0,
        gpu_units: float = 0.0, job_type: str = "",
        declared: Optional[Dict[str, float]] = None,
        strategy: SelectionStrategy = SelectionStrategy.BALANCED,
        region: Optional[str] = None, zone: Optional[str] = None,
        preferred_nodes: Optional[List[str]] = None,
        required_labels: Optional[Dict[str, str]] = None,
    ) -> PlacementPlan:
        """Generate a placement plan for a single job."""

        # 1. Estimate resources
        estimate = self._estimator.estimate(job_id, job_type, declared)

        cpu = cpu_cores or estimate.cpu_cores
        mem = memory_mb or estimate.memory_mb
        gpu = gpu_units or estimate.gpu_units

        # 2. Apply affinity to expand preferred nodes
        affinity_nodes = self._resolve_affinity(job_id, preferred_nodes or [])

        # 3. Apply anti-affinity to exclude nodes
        excluded = self._resolve_anti_affinity(job_id)

        # 4. Topology-aware filtering
        topo_preferred = self._resolve_topology(job_id, region, zone)

        # 5. Select best node
        selected = self._selector.select(
            cpu_cores=cpu, memory_mb=mem, gpu_units=gpu,
            strategy=strategy, region=region, zone=zone,
            preferred_nodes=list(set(affinity_nodes + topo_preferred)),
            required_labels=required_labels,
        )

        plan = PlacementPlan()
        if selected is None:
            plan.status = "failed_no_capacity"
            return plan

        # 6. Build assignment
        score = self._selector._scorer.best_node(
            self._inventory.filter(min_cpu=cpu, min_memory_mb=mem),
            cpu, mem,
        )
        assignment = PlacementAssignment(
            job_id=job_id, node_id=selected.node_id,
            cpu_cores=cpu, memory_mb=mem, gpu_units=gpu,
            score=score.total_score if score else 0.0,
            reason=f"strategy={strategy.value}",
        )
        plan.assignments.append(assignment)
        plan.status = "ready"

        logger.debug(
            "PlacementPlanner: job=%s → node=%s (score=%.3f)",
            job_id, selected.node_id, assignment.score,
        )
        return plan

    async def plan_batch(
        self, jobs: List[Dict[str, Any]],
        strategy: SelectionStrategy = SelectionStrategy.BALANCED,
    ) -> PlacementPlan:
        """Plan placement for multiple jobs."""
        plan = PlacementPlan()
        for job in jobs:
            sub_plan = await self.plan(**job)
            plan.assignments.extend(sub_plan.assignments)
            if sub_plan.status.startswith("failed"):
                plan.status = "partial"
        if plan.status == "pending":
            plan.status = "ready"
        return plan

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_affinity(self, rule: AffinityRule) -> None:
        self._affinity_rules.append(rule)

    def add_anti_affinity(self, rule: AntiAffinityRule) -> None:
        self._anti_affinity_rules.append(rule)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_affinity(self, job_id: str, preferred: List[str]) -> List[str]:
        result = list(preferred)
        for rule in self._affinity_rules:
            if rule.matches(job_id):
                result.extend(rule.target_nodes)
        return result

    def _resolve_anti_affinity(self, job_id: str) -> List[str]:
        excluded: List[str] = []
        for rule in self._anti_affinity_rules:
            if rule.matches(job_id):
                excluded.extend(rule.target_nodes)
        return excluded

    def _resolve_topology(
        self, job_id: str, region: Optional[str], zone: Optional[str],
    ) -> List[str]:
        if self._topology is None:
            return []
        return self._topology.get_preferred_nodes(job_id, region, zone)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "selector": self._selector.health_report(),
            "estimator": self._estimator.health_report(),
            "affinity_rules": len(self._affinity_rules),
            "anti_affinity_rules": len(self._anti_affinity_rules),
        }
