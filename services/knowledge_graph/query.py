"""Graph Query Engine – neighbors, shortest path, subgraph, pattern, traversal."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from .graph_builder import GraphBuilder


class GraphQueryEngine:
    """Query engine for the financial knowledge graph.

    Supports: neighbor search, shortest path, subgraph extraction,
    pattern matching, and BFS/DFS traversal.
    """

    def neighbors(self, graph: GraphBuilder, node: str) -> List[str]:
        """Return direct neighbor entity ids (outgoing edges).

        Args:
            graph: the knowledge graph.
            node: entity id to query.

        Returns:
            List of target entity ids.
        """
        return [e[1] for e in graph.edges if e[0] == node]

    def neighbors_with_relations(
        self,
        graph: GraphBuilder,
        node: str,
    ) -> List[Tuple[str, str, float]]:
        """Return outgoing neighbors with (target, relation, weight)."""
        return graph.get_neighbors(node)

    def all_neighbors(self, graph: GraphBuilder, node: str) -> List[str]:
        """Return all connected neighbors (outgoing + incoming)."""
        outgoing = {e[1] for e in graph.edges if e[0] == node}
        incoming = {e[0] for e in graph.edges if e[1] == node}
        return list(outgoing | incoming)

    def shortest_path(
        self,
        graph: GraphBuilder,
        source: str,
        target: str,
    ) -> Optional[List[str]]:
        """BFS shortest path from source to target.

        Args:
            graph: the knowledge graph.
            source: starting entity id.
            target: ending entity id.

        Returns:
            List of entity ids forming the shortest path, or None.
        """
        if source == target:
            return [source]

        adj: Dict[str, List[str]] = {}
        for s, t, _, _ in graph.edges:
            adj.setdefault(s, []).append(t)

        if source not in adj:
            return None

        visited = {source: None}
        queue = deque([source])

        while queue:
            current = queue.popleft()
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited[neighbor] = current
                    if neighbor == target:
                        # Reconstruct path
                        path = []
                        node: Optional[str] = target
                        while node is not None:
                            path.append(node)
                            node = visited[node]
                        return path[::-1]
                    queue.append(neighbor)

        return None

    def find_paths_by_relation(
        self,
        graph: GraphBuilder,
        source: str,
        relation: str,
        max_depth: int = 3,
    ) -> List[List[str]]:
        """Find all paths from source following a specific relation type.

        Args:
            graph: the knowledge graph.
            source: starting entity id.
            relation: relation type to follow.
            max_depth: maximum path length.

        Returns:
            List of paths (each path is a list of entity ids).
        """
        paths: List[List[str]] = []

        def dfs(current: str, path: List[str], depth: int) -> None:
            if depth > max_depth:
                return
            for s, t, r, _ in graph.edges:
                if s == current and r == relation and t not in path:
                    new_path = path + [t]
                    paths.append(new_path)
                    dfs(t, new_path, depth + 1)

        dfs(source, [source], 1)
        return paths

    def subgraph_around(
        self,
        graph: GraphBuilder,
        node: str,
        depth: int = 2,
    ) -> GraphBuilder:
        """Extract the neighborhood subgraph around a node up to given depth."""
        visited: Set[str] = {node}
        frontier = {node}
        for _ in range(depth):
            next_frontier: Set[str] = set()
            for current in frontier:
                for s, t, _, _ in graph.edges:
                    if s == current and t not in visited:
                        next_frontier.add(t)
                        visited.add(t)
                    if t == current and s not in visited:
                        next_frontier.add(s)
                        visited.add(s)
            frontier = next_frontier
        return graph.subgraph(visited)

    def degree_centrality(self, graph: GraphBuilder) -> Dict[str, int]:
        """Compute degree centrality (outgoing + incoming edges) for each node."""
        centrality: Dict[str, int] = {nid: 0 for nid in graph.nodes}
        for s, t, _, _ in graph.edges:
            if s in centrality:
                centrality[s] += 1
            if t in centrality:
                centrality[t] += 1
        return centrality

    def top_central_nodes(
        self,
        graph: GraphBuilder,
        n: int = 10,
    ) -> List[Tuple[str, int]]:
        """Return top-N most central nodes."""
        centrality = self.degree_centrality(graph)
        sorted_items = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def find_by_relation(
        self,
        graph: GraphBuilder,
        source: str,
        relation: str,
    ) -> List[str]:
        """Find all neighbors of source connected by a specific relation."""
        return [e[1] for e in graph.edges if e[0] == source and e[2] == relation]
