"""
Critical Path Analyzer — identifies the critical path (longest execution path) in the DAG.

Used for:
- Performance optimization (focus on bottleneck nodes)
- Scheduling optimization (prioritize critical path nodes)
- SLA estimation (predict total execution time)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.workflow.dag.dag import DAG
from services.workflow.dag.topological_sort import TopologicalSort, TopologicalResult

logger = logging.getLogger(__name__)


@dataclass
class CriticalPathResult:
    """Result of critical path analysis."""

    critical_path: List[str]          # Nodes on the critical path (ordered)
    critical_path_length: float       # Total weight/latency on critical path
    node_earliest_start: Dict[str, float]  # Earliest start time per node
    node_latest_start: Dict[str, float]    # Latest start time per node
    node_slack: Dict[str, float]           # Slack time per node (0 = critical)
    total_nodes: int
    critical_node_count: int
    bottleneck_nodes: List[str]       # Nodes with highest individual weight


class CriticalPathAnalyzer:
    """
    Analyzes the DAG to find the critical path.

    Uses the Critical Path Method (CPM):
    1. Forward pass: compute earliest start times
    2. Backward pass: compute latest start times
    3. Slack = LST - EST → zero slack = critical path
    """

    def __init__(self, topo_sort: Optional[TopologicalSort] = None):
        self.topo_sort = topo_sort or TopologicalSort()

    def analyze(
        self,
        dag: DAG,
        node_weights: Optional[Dict[str, float]] = None,
    ) -> CriticalPathResult:
        """
        Analyze the DAG's critical path.

        Args:
            dag: The DAG to analyze.
            node_weights: Estimated execution time per node (default: 1.0).

        Returns:
            CriticalPathResult with detailed analysis.
        """
        topo_result = self.topo_sort.sort(dag)
        if not topo_result.is_valid:
            raise ValueError("Cannot analyze invalid DAG")

        linear_order = topo_result.linear_order
        weights = node_weights or {nid: 1.0 for nid in dag.nodes}

        # Forward pass: compute earliest start times
        est: Dict[str, float] = {nid: 0.0 for nid in dag.nodes}
        for node_id in linear_order:
            for pred in dag.get_predecessors(node_id):
                est[node_id] = max(est[node_id], est[pred] + weights.get(pred, 1.0))

        # Backward pass: compute latest start times
        max_finish = max(
            est[nid] + weights.get(nid, 1.0)
            for nid in dag.nodes
        )
        lst: Dict[str, float] = {nid: max_finish for nid in dag.nodes}
        for node_id in reversed(linear_order):
            node_weight = weights.get(node_id, 1.0)
            for succ in dag.get_successors(node_id):
                lst[node_id] = min(lst[node_id], lst[succ] - node_weight)

        # Compute slack and identify critical path
        slack: Dict[str, float] = {}
        critical_nodes: List[str] = []
        for node_id in linear_order:
            s = lst[node_id] - est[node_id]
            slack[node_id] = s
            if abs(s) < 1e-9:
                critical_nodes.append(node_id)

        # Sort critical nodes by EST to get the path
        critical_nodes.sort(key=lambda nid: est[nid])

        # Find bottleneck nodes (top 3 by weight)
        sorted_by_weight = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        bottleneck_nodes = [nid for nid, _ in sorted_by_weight[:3]]

        return CriticalPathResult(
            critical_path=critical_nodes,
            critical_path_length=max_finish,
            node_earliest_start=est,
            node_latest_start=lst,
            node_slack=slack,
            total_nodes=dag.node_count,
            critical_node_count=len(critical_nodes),
            bottleneck_nodes=bottleneck_nodes,
        )

    def get_estimated_duration(
        self,
        dag: DAG,
        node_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Get the estimated total duration of the DAG (critical path length)."""
        result = self.analyze(dag, node_weights)
        return result.critical_path_length
