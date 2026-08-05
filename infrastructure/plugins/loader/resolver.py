"""Dependency resolver for the plugin loader subsystem.

Resolves plugin dependencies using a directed dependency graph with:

- Optional dependencies (prefixed with ``?``)
- Cycle detection via DFS
- Topological sort via Kahn's algorithm
- Missing dependency detection
- Version constraint checking (``>=``, ``<=``, ``>``, ``<``, ``==``,
  ``!=``, ``~=``)
- Transitive load-order resolution for individual plugins

The graph maps ``plugin_id -> set(dependency_ids)`` where an edge
``a -> b`` means ``a`` depends on ``b`` (``b`` must load before
``a``).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set

from ..utils import compare_versions, parse_version

logger = logging.getLogger(__name__)


class DependencyResolver2:
    """Resolves plugin dependencies with cycle detection and ordering.

    The graph maps ``plugin_id -> set(dependency_ids)`` where an edge
    ``a -> b`` means ``a`` depends on ``b`` (``b`` must load before
    ``a``).

    Supports optional dependencies (prefixed with ``?``) and version
    constraints (``>=``, ``<=``, ``>``, ``<``, ``==``, ``!=``, ``~=``).
    """

    def __init__(self) -> None:
        self._last_resolution: Optional[Dict[str, Any]] = None
        self._resolution_count: int = 0
        self._cycle_count: int = 0
        self._missing_count: int = 0

    def resolve(
        self,
        plugins: Dict[str, List[str]],
        available: Set[str],
    ) -> Dict[str, Any]:
        """Resolve dependencies across all plugins.

        Builds the dependency graph, detects cycles, identifies
        missing required dependencies, and computes a topological
        load order when the graph is valid.

        Args:
            plugins: Map of plugin id to its list of dependency
                ids (optionally with ``?`` prefix for optional deps).
            available: Set of currently available plugin ids.

        Returns:
            Resolution dictionary with keys:

            - ``valid``: ``True`` when no cycles and no missing deps.
            - ``order``: Topological load order (empty when invalid).
            - ``cycles``: List of detected cycles.
            - ``missing``: Map of plugin id to its missing required deps.
            - ``graph``: The raw dependency graph.
            - ``optional``: Map of plugin id to its optional dep set.
        """
        start = time.monotonic()
        self._resolution_count += 1

        optional: Dict[str, Set[str]] = {}
        for pid, deps in plugins.items():
            opt_set: Set[str] = set()
            for dep in deps or []:
                if dep.startswith("?") and len(dep) > 1:
                    opt_set.add(dep[1:])
            if opt_set:
                optional[pid] = opt_set

        graph = self.build_graph(plugins)
        cycles = self.detect_cycles(graph)
        missing = self._find_missing(graph, available, optional)

        if not cycles and not missing:
            order = self.topological_sort(graph)
            valid = True
        else:
            order = []
            valid = False

        if cycles:
            self._cycle_count += len(cycles)
        if missing:
            self._missing_count += sum(len(v) for v in missing.values())

        result: Dict[str, Any] = {
            "valid": valid,
            "order": order,
            "cycles": cycles,
            "missing": missing,
            "graph": {k: sorted(v) for k, v in graph.items()},
            "optional": {k: sorted(v) for k, v in optional.items()},
        }
        self._last_resolution = result

        elapsed_ms = (time.monotonic() - start) * 1000.0
        logger.debug(
            "Resolved dependencies for %d plugins in %.2f ms "
            "(valid=%s, cycles=%d, missing=%d).",
            len(plugins),
            elapsed_ms,
            valid,
            len(cycles),
            len(missing),
        )
        return result

    def build_graph(
        self, plugins: Dict[str, List[str]]
    ) -> Dict[str, Set[str]]:
        """Build a dependency graph from a plugin-to-deps mapping.

        Optional dependencies (prefixed with ``?``) are stripped of
        their prefix. Nodes for dependencies not in ``plugins`` are
        added with empty dependency sets.

        Args:
            plugins: Map of plugin id to its raw dependency list.

        Returns:
            Dict mapping each plugin id to a set of its dependency ids.
        """
        graph: Dict[str, Set[str]] = {}
        for plugin_id, deps in plugins.items():
            graph[plugin_id] = set()
            for dep in deps or []:
                clean_dep = dep[1:] if dep.startswith("?") else dep
                if not clean_dep:
                    continue
                graph[plugin_id].add(clean_dep)
                if clean_dep not in graph:
                    graph[clean_dep] = set()
        return graph

    def detect_cycles(
        self, graph: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """Detect cycles in the dependency graph using DFS.

        Args:
            graph: Dependency graph from :meth:`build_graph`.

        Returns:
            List of cycles, each represented as a list of plugin ids
            forming the cycle (with the start node repeated at the end).
        """
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in sorted(graph.get(node, set())):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    try:
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        cycles.append(cycle)
                    except ValueError:
                        cycles.append([neighbor, node, neighbor])
            rec_stack.discard(node)
            path.pop()

        for node in sorted(graph):
            if node not in visited:
                dfs(node)
        return cycles

    def topological_sort(
        self, graph: Dict[str, Set[str]]
    ) -> List[str]:
        """Return a topological ordering of the graph via Kahn's algorithm.

        Nodes with no dependencies come first. Ties are broken
        alphabetically for deterministic output. If the graph contains
        cycles, the remaining nodes are appended in sorted order.

        Args:
            graph: Dependency graph from :meth:`build_graph`.

        Returns:
            Topological ordering of plugin ids.
        """
        in_degree: Dict[str, int] = {node: 0 for node in graph}
        for node, deps in graph.items():
            for dep in deps:
                if dep not in in_degree:
                    in_degree[dep] = 0
            in_degree[node] = len(deps)

        reverse_graph: Dict[str, Set[str]] = {
            node: set() for node in in_degree
        }
        for node, deps in graph.items():
            for dep in deps:
                if dep not in reverse_graph:
                    reverse_graph[dep] = set()
                reverse_graph[dep].add(node)

        queue: deque[str] = deque(
            sorted(n for n, deg in in_degree.items() if deg == 0)
        )
        result: List[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in sorted(reverse_graph.get(node, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    inserted = False
                    for i, existing in enumerate(queue):
                        if dependent < existing:
                            queue.insert(i, dependent)
                            inserted = True
                            break
                    if not inserted:
                        queue.append(dependent)

        if len(result) != len(in_degree):
            remaining = sorted(
                n for n in in_degree if n not in set(result)
            )
            result.extend(remaining)
        return result

    def check_version_constraint(
        self, required: str, available: str
    ) -> bool:
        """Check whether ``available`` satisfies the ``required`` constraint.

        Supports the operators ``>=``, ``<=``, ``>``, ``<``, ``==``,
        ``!=``, and ``~=``. A bare version string is treated as
        ``>=``.

        Args:
            required: Version constraint string (e.g. ``">=1.0.0"``).
            available: Actual version string.

        Returns:
            ``True`` if the available version satisfies the constraint.
        """
        if not required or not available:
            return False

        constraint = required.strip()

        if constraint.startswith(">="):
            return compare_versions(available, constraint[2:].strip()) >= 0
        if constraint.startswith("<="):
            return compare_versions(available, constraint[2:].strip()) <= 0
        if constraint.startswith("!="):
            return compare_versions(available, constraint[2:].strip()) != 0
        if constraint.startswith("=="):
            return compare_versions(available, constraint[2:].strip()) == 0
        if constraint.startswith("~="):
            target = constraint[2:].strip()
            req_parts = parse_version(target)
            avail_parts = parse_version(available)
            if len(req_parts) < 2:
                return compare_versions(available, target) == 0
            prefix_len = len(req_parts) - 1
            if len(avail_parts) < prefix_len:
                return False
            return (
                avail_parts[:prefix_len] == req_parts[:prefix_len]
                and compare_versions(available, target) >= 0
            )
        if constraint.startswith(">"):
            return compare_versions(available, constraint[1:].strip()) > 0
        if constraint.startswith("<"):
            return compare_versions(available, constraint[1:].strip()) < 0

        return compare_versions(available, constraint) >= 0

    def get_load_order(
        self,
        plugin_id: str,
        all_plugins: Dict[str, List[str]],
    ) -> List[str]:
        """Get the ordered load queue for a single plugin.

        Resolves transitive dependencies and returns a topological
        ordering where dependencies appear before the requested
        plugin.

        Args:
            plugin_id: The plugin id to resolve.
            all_plugins: Map of all plugin ids to their dependency lists.

        Returns:
            Ordered list of plugin ids to load before the requested
            plugin (including the plugin itself at the end).
        """
        if plugin_id not in all_plugins:
            return [plugin_id]

        visited: Set[str] = set()
        order: List[str] = []

        def collect_deps(pid: str) -> None:
            if pid in visited:
                return
            visited.add(pid)
            deps = all_plugins.get(pid, [])
            for dep in deps:
                clean_dep = dep[1:] if dep.startswith("?") else dep
                if clean_dep and clean_dep in all_plugins:
                    collect_deps(clean_dep)
            order.append(pid)

        collect_deps(plugin_id)
        return order

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the resolver state to a dictionary."""
        return {
            "resolution_count": self._resolution_count,
            "cycle_count": self._cycle_count,
            "missing_count": self._missing_count,
            "last_resolution": self._last_resolution,
        }

    def _find_missing(
        self,
        graph: Dict[str, Set[str]],
        available: Set[str],
        optional: Dict[str, Set[str]],
    ) -> Dict[str, List[str]]:
        """Find required dependencies that are not available.

        Optional dependencies are excluded from the missing set.

        Args:
            graph: Dependency graph.
            available: Set of available plugin ids.
            optional: Map of plugin id to its optional dependency set.

        Returns:
            Map of plugin id to its list of missing required deps.
        """
        missing: Dict[str, List[str]] = {}
        for plugin_id, deps in graph.items():
            missing_deps: List[str] = []
            opt_set = optional.get(plugin_id, set())
            for dep in deps:
                if dep in available:
                    continue
                if dep in opt_set:
                    continue
                missing_deps.append(dep)
            if missing_deps:
                missing[plugin_id] = sorted(missing_deps)
        return missing