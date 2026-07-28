"""Causal Graph Engine – establishes cause-effect relationships for reasoning."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from .graph_builder import GraphBuilder


class CausalGraphEngine:
    """Builds and queries causal reasoning graphs for macro and market analysis.

    Causal edges represent: A CAUSES B (A → B).
    """

    def __init__(self) -> None:
        self._causal_graph: GraphBuilder = GraphBuilder()

    def infer(self, cause: str) -> Dict[str, Any]:
        """Return a minimal causal inference result (basic spec compliance).

        Args:
            cause: the cause entity.

        Returns:
            Dict with cause and effect.
        """
        return {"cause": cause, "effect": "UNKNOWN"}

    def add_causal_link(
        self,
        cause: str,
        effect: str,
        confidence: float = 1.0,
    ) -> None:
        """Add a causal relationship: cause → effect.

        Args:
            cause: causal entity id.
            effect: effect entity id.
            confidence: confidence in the causal relationship (0-1).
        """
        self._causal_graph.add_edge(cause, effect, "causes", confidence)

    def add_causal_chain(self, chain: List[str], confidence: float = 1.0) -> None:
        """Add a chain of causes: A → B → C → ...

        Args:
            chain: ordered list of entity ids.
            confidence: confidence of each link.
        """
        for i in range(len(chain) - 1):
            self._causal_graph.add_edge(chain[i], chain[i + 1], "causes", confidence)

    def get_effects(self, cause: str) -> List[Tuple[str, float]]:
        """Return all direct effects of a cause.

        Args:
            cause: cause entity id.

        Returns:
            List of (effect, confidence) tuples.
        """
        return [(e[1], e[3]) for e in self._causal_graph.edges if e[0] == cause]

    def get_causes(self, effect: str) -> List[Tuple[str, float]]:
        """Return all direct causes of an effect.

        Args:
            effect: effect entity id.

        Returns:
            List of (cause, confidence) tuples.
        """
        return [(e[0], e[3]) for e in self._causal_graph.edges if e[1] == effect]

    def downstream_effects(
        self,
        cause: str,
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find all downstream effects of a cause up to max_depth.

        Args:
            cause: starting cause entity.
            max_depth: maximum causal chain length.

        Returns:
            List of {"entity": str, "depth": int, "confidence": float} dicts.
        """
        results: List[Dict[str, Any]] = []
        visited: Set[str] = set()
        queue = deque([(cause, 0, 1.0)])

        while queue:
            current, depth, cumulative_conf = queue.popleft()
            if depth > max_depth:
                continue
            visited.add(current)
            if depth > 0:
                results.append({
                    "entity": current,
                    "depth": depth,
                    "confidence": round(cumulative_conf, 4),
                })
            for _, target, _, conf in self._causal_graph.edges:
                if _ == current and target not in visited:
                    new_conf = cumulative_conf * conf
                    queue.append((target, depth + 1, new_conf))

        return results

    def upstream_causes(
        self,
        effect: str,
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find all upstream causes of an effect up to max_depth.

        Args:
            effect: target effect entity.
            max_depth: maximum causal chain length.

        Returns:
            List of {"entity": str, "depth": int, "confidence": float} dicts.
        """
        results: List[Dict[str, Any]] = []
        visited: Set[str] = set()
        queue = deque([(effect, 0, 1.0)])

        while queue:
            current, depth, cumulative_conf = queue.popleft()
            if depth > max_depth:
                continue
            visited.add(current)
            if depth > 0:
                results.append({
                    "entity": current,
                    "depth": depth,
                    "confidence": round(cumulative_conf, 4),
                })
            for source, _, _, conf in self._causal_graph.edges:
                if _ == current and source not in visited:
                    new_conf = cumulative_conf * conf
                    queue.append((source, depth + 1, new_conf))

        return results

    def causal_chain(self, chain: List[str]) -> float:
        """Compute the cumulative confidence of a causal chain.

        Args:
            chain: ordered list of entity ids forming a chain.

        Returns:
            Cumulative confidence (product of all link confidences, or 0 if broken).
        """
        if len(chain) < 2:
            return 1.0

        cumulative = 1.0
        for i in range(len(chain) - 1):
            found = False
            for s, t, _, conf in self._causal_graph.edges:
                if s == chain[i] and t == chain[i + 1]:
                    cumulative *= conf
                    found = True
                    break
            if not found:
                return 0.0
        return round(cumulative, 4)

    @property
    def link_count(self) -> int:
        return self._causal_graph.edge_count

    def clear(self) -> None:
        self._causal_graph = GraphBuilder()
