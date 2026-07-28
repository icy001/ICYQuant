"""Event Propagation Engine – simulates event influence cascades through the knowledge graph."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set

from .graph_builder import GraphBuilder


class EventPropagationEngine:
    """Simulates how events (e.g. rate cuts, news) propagate through the graph.

    Uses BFS-based ripple propagation with configurable decay and depth limit.
    """

    def __init__(self, max_depth: int = 5, decay_factor: float = 0.7) -> None:
        self.max_depth = max_depth
        self.decay_factor = decay_factor

    def propagate(self, event: str) -> Dict[str, Any]:
        """Return a minimal propagation result (basic spec compliance).

        Args:
            event: event name or identifier.

        Returns:
            Dict with event and status.
        """
        return {"event": event, "status": "PROPAGATED"}

    def propagate_through_graph(
        self,
        graph: GraphBuilder,
        source: str,
        initial_impact: float = 1.0,
    ) -> Dict[str, Any]:
        """Propagate an event's impact from source through the graph.

        Each step the impact decays by decay_factor. Returns affected nodes
        and their impact scores.

        Args:
            graph: the knowledge graph.
            source: the entity where the event originates.
            initial_impact: initial impact strength (0-1).

        Returns:
            Dict with affected nodes, propagation paths, and scores.
        """
        if source not in graph.nodes:
            return {"event": source, "status": "UNKNOWN_SOURCE", "affected": []}

        impact_scores: Dict[str, float] = {source: initial_impact}
        paths: Dict[str, List[str]] = {source: [source]}
        queue = deque([(source, 0, initial_impact)])

        while queue:
            current, depth, impact = queue.popleft()
            if depth >= self.max_depth:
                continue

            # Traverse outgoing edges from current node
            for s, t, r, w in graph.edges:
                if s == current:
                    new_impact = impact * self.decay_factor * w
                    if t not in impact_scores or new_impact > impact_scores[t]:
                        impact_scores[t] = new_impact
                        paths[t] = paths[current] + [t]
                        queue.append((t, depth + 1, new_impact))

        # Sort by impact descending
        affected = sorted(
            [{"entity": nid, "impact": round(score, 4), "path": paths.get(nid, [])}
             for nid, score in impact_scores.items() if nid != source],
            key=lambda x: x["impact"], reverse=True,
        )

        return {
            "event": source,
            "status": "PROPAGATED",
            "initial_impact": initial_impact,
            "max_depth": self.max_depth,
            "decay_factor": self.decay_factor,
            "affected_count": len(affected),
            "affected": affected,
        }

    def find_influence_path(
        self,
        graph: GraphBuilder,
        source: str,
        target: str,
        relation_filter: Optional[str] = None,
    ) -> Optional[List[str]]:
        """Find a propagation path from source to target.

        Args:
            graph: the knowledge graph.
            source: origin entity.
            target: destination entity.
            relation_filter: optional relation type to restrict traversal.

        Returns:
            List of entity ids forming the path, or None.
        """
        if source == target:
            return [source]

        visited = {source: None}
        queue = deque([source])

        while queue:
            current = queue.popleft()
            for s, t, r, _ in graph.edges:
                if s != current:
                    continue
                if relation_filter and r != relation_filter:
                    continue
                if t not in visited:
                    visited[t] = current
                    if t == target:
                        path = []
                        node: Optional[str] = target
                        while node is not None:
                            path.append(node)
                            node = visited[node]
                        return path[::-1]
                    queue.append(t)

        return None
