"""Dependency resolver.

Resolves plugin dependencies with circular detection, topological
sorting, missing dependency detection, and version constraint checking.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from .utils import compare_versions, parse_version

logger = logging.getLogger(__name__)


class DependencyResolver:
    """Resolves plugin dependencies with circular detection and topological sort.

    Supports:
    - Circular dependency detection
    - Missing dependency detection
    - Version constraint checking
    - Optional dependencies
    - Topological sort for load order
    """

    def __init__(self) -> None:
        self._last_resolution: Optional[Dict[str, Any]] = None

    def build_graph(self, plugins: Dict[str, List[str]]) -> Dict[str, Set[str]]:
        graph: Dict[str, Set[str]] = {}
        for plugin_id, deps in plugins.items():
            graph[plugin_id] = set()
            for dep in deps:
                # Strip optional prefix for graph building
                clean_dep = dep
                if dep.startswith("?"):
                    clean_dep = dep[1:]
                graph[plugin_id].add(clean_dep)
                if clean_dep not in graph:
                    graph[clean_dep] = set()
        return graph

    def detect_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            rec_stack.discard(node)
            path.pop()

        for node in graph:
            if node not in visited:
                dfs(node)
        return cycles

    def topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        in_degree: Dict[str, int] = {node: 0 for node in graph}
        for node, deps in graph.items():
            for dep in deps:
                if dep not in in_degree:
                    in_degree[dep] = 0
                # node depends on dep, so dep has an edge TO node
                # node is a dependent of dep
                in_degree[node] += 1

        # Build reverse graph: dep -> set of nodes that depend on dep
        reverse_graph: Dict[str, Set[str]] = {node: set() for node in in_degree}
        for node in graph:
            for dep in graph.get(node, set()):
                if dep not in reverse_graph:
                    reverse_graph[dep] = set()
                reverse_graph[dep].add(node)

        from collections import deque
        queue = deque(sorted(n for n, deg in in_degree.items() if deg == 0))
        result: List[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in sorted(reverse_graph.get(node, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        if len(result) != len(graph):
            remaining = [n for n in graph if n not in set(result)]
            result.extend(sorted(remaining))
        return result

    def find_missing(
        self,
        graph: Dict[str, Set[str]],
        available: Set[str],
        optional_deps: Optional[Dict[str, Set[str]]] = None,
    ) -> Dict[str, List[str]]:
        missing: Dict[str, List[str]] = {}
        opt_deps = optional_deps or {}
        for plugin_id, deps in graph.items():
            missing_deps = []
            for d in deps:
                if d not in available:
                    if plugin_id in opt_deps and d in opt_deps[plugin_id]:
                        continue  # skip optional dep
                    missing_deps.append(d)
            if missing_deps:
                missing[plugin_id] = sorted(missing_deps)
        return missing

    def resolve(
        self, plugins: Dict[str, List[str]], available: Set[str]
    ) -> Dict[str, Any]:
        # Identify optional deps (prefixed with ?)
        optional: Dict[str, Set[str]] = {}
        for pid, deps in plugins.items():
            opt_set = set()
            for d in deps:
                if d.startswith("?"):
                    opt_set.add(d[1:])
            if opt_set:
                optional[pid] = opt_set

        graph = self.build_graph(plugins)
        cycles = self.detect_cycles(graph)
        missing = self.find_missing(graph, available, optional)
        if not cycles and not missing:
            order = self.topological_sort(graph)
            valid = True
        else:
            order = []
            valid = False
        result: Dict[str, Any] = {
            "order": order,
            "cycles": cycles,
            "missing": missing,
            "valid": valid,
            "optional": {k: sorted(v) for k, v in optional.items()},
            "graph": {k: sorted(v) for k, v in graph.items()},
        }
        self._last_resolution = result
        return result

    def check_version_constraint(self, required: str, available: str) -> bool:
        if not required or not available:
            return False
        constraint = required.strip()
        if constraint.startswith(">="):
            req_ver = constraint[2:].strip()
            return compare_versions(available, req_ver) >= 0
        elif constraint.startswith("<="):
            req_ver = constraint[2:].strip()
            return compare_versions(available, req_ver) <= 0
        elif constraint.startswith(">"):
            req_ver = constraint[1:].strip()
            return compare_versions(available, req_ver) > 0
        elif constraint.startswith("<"):
            req_ver = constraint[1:].strip()
            return compare_versions(available, req_ver) < 0
        elif constraint.startswith("=="):
            req_ver = constraint[2:].strip()
            return compare_versions(available, req_ver) == 0
        elif constraint.startswith("!="):
            req_ver = constraint[2:].strip()
            return compare_versions(available, req_ver) != 0
        elif constraint.startswith("~="):
            req_ver = constraint[2:].strip()
            req_parts = parse_version(req_ver)
            avail_parts = parse_version(available)
            if len(req_parts) < 2:
                return compare_versions(available, req_ver) == 0
            prefix_len = len(req_parts) - 1
            if len(avail_parts) < prefix_len:
                return False
            return avail_parts[:prefix_len] == req_parts[:prefix_len] and compare_versions(available, req_ver) >= 0
        else:
            return compare_versions(available, constraint) >= 0

    def get_dependency_tree(
        self, plugin_id: str, graph: Dict[str, Set[str]]
    ) -> Dict[str, Any]:
        visited: Set[str] = set()

        def build_tree(pid: str) -> Dict[str, Any]:
            if pid in visited:
                return {"id": pid, "circular": True, "children": []}
            visited.add(pid)
            deps = graph.get(pid, set())
            children = [build_tree(d) for d in sorted(deps)]
            return {"id": pid, "circular": False, "children": children}

        return build_tree(plugin_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_resolution": self._last_resolution,
        }