"""
Cycle Detector — detects cycles in the DAG using DFS with back-edge detection.

A DAG must be acyclic by definition. If a cycle is detected, the workflow
definition is invalid and must be rejected.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from services.workflow.dag.dag import DAG

logger = logging.getLogger(__name__)


class DFSColor(str, Enum):
    WHITE = "white"   # Not visited
    GRAY = "gray"     # In current DFS path
    BLACK = "black"   # Fully processed


class CycleDetector:
    """
    Detects cycles in a DAG using DFS with coloring.

    Algorithm:
    1. Mark all nodes WHITE.
    2. For each WHITE node, start DFS.
    3. Mark node GRAY when entering.
    4. If we encounter a GRAY node, we found a back-edge → cycle.
    5. Mark node BLACK when exiting (all descendants processed).
    """

    def __init__(self):
        pass

    def detect(self, dag: DAG) -> Tuple[bool, List[str]]:
        """
        Detect cycles in the DAG.

        Returns:
            (has_cycle, cycle_path) — True and the cycle node list if found.
        """
        color: Dict[str, DFSColor] = {nid: DFSColor.WHITE for nid in dag.nodes}
        parent: Dict[str, Optional[str]] = {nid: None for nid in dag.nodes}

        for node_id in dag.nodes:
            if color[node_id] == DFSColor.WHITE:
                has_cycle, cycle = self._dfs(node_id, color, parent, dag)
                if has_cycle:
                    return True, cycle

        return False, []

    def _dfs(
        self,
        node_id: str,
        color: Dict[str, DFSColor],
        parent: Dict[str, Optional[str]],
        dag: DAG,
    ) -> Tuple[bool, List[str]]:
        """DFS traversal with cycle detection."""
        color[node_id] = DFSColor.GRAY

        for successor in dag.get_successors(node_id):
            if color.get(successor) == DFSColor.GRAY:
                # Back-edge found: cycle detected
                cycle = self._extract_cycle(node_id, successor, parent)
                return True, cycle
            if color.get(successor) == DFSColor.WHITE:
                parent[successor] = node_id
                has_cycle, cycle = self._dfs(successor, color, parent, dag)
                if has_cycle:
                    return True, cycle

        color[node_id] = DFSColor.BLACK
        return False, []

    def _extract_cycle(
        self, start: str, end: str, parent: Dict[str, Optional[str]]
    ) -> List[str]:
        """Extract the cycle path from parent pointers."""
        cycle = [end, start]
        current = start
        while parent.get(current) and parent[current] != end:
            current = parent[current]
            cycle.append(current)
        cycle.append(end)
        cycle.reverse()
        return cycle

    def detect_all_cycles(self, dag: DAG) -> List[List[str]]:
        """Detect all cycles (for debugging). Returns list of cycles."""
        cycles: List[List[str]] = []
        color: Dict[str, DFSColor] = {nid: DFSColor.WHITE for nid in dag.nodes}
        parent: Dict[str, Optional[str]] = {nid: None for nid in dag.nodes}

        for node_id in dag.nodes:
            if color[node_id] == DFSColor.WHITE:
                self._dfs_all(node_id, color, parent, dag, cycles)

        return cycles

    def _dfs_all(
        self,
        node_id: str,
        color: Dict[str, DFSColor],
        parent: Dict[str, Optional[str]],
        dag: DAG,
        cycles: List[List[str]],
    ) -> None:
        color[node_id] = DFSColor.GRAY
        for successor in dag.get_successors(node_id):
            if color.get(successor) == DFSColor.GRAY:
                cycle = self._extract_cycle(node_id, successor, parent)
                cycles.append(cycle)
            elif color.get(successor) == DFSColor.WHITE:
                parent[successor] = node_id
                self._dfs_all(successor, color, parent, dag, cycles)
        color[node_id] = DFSColor.BLACK
