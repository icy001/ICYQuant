"""Factor Graph – maintains the inter-relationship network of financial factors."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .graph_builder import GraphBuilder


class FactorGraph:
    """Builds and queries the factor inter-relationship network.

    Factors: Momentum, Quality, Value, Growth, Liquidity, Volatility, Size, etc.
    Relationships: correlation, complement, substitute, derived_from.
    """

    def __init__(self) -> None:
        self._graph: GraphBuilder = GraphBuilder()
        self._factor_definitions: Dict[str, Dict[str, Any]] = {}

    def link(self, factor_a: str, factor_b: str) -> Tuple[str, str]:
        """Basic link between two factors.

        Args:
            factor_a: first factor id.
            factor_b: second factor id.

        Returns:
            Tuple of (factor_a, factor_b).
        """
        return (factor_a, factor_b)

    def define_factor(
        self,
        factor_id: str,
        name: str,
        category: str = "style",
        description: str = "",
    ) -> None:
        """Define a factor with metadata."""
        self._factor_definitions[factor_id] = {
            "name": name,
            "category": category,
            "description": description,
        }

    def add_correlation(
        self,
        factor_a: str,
        factor_b: str,
        correlation: float,
    ) -> None:
        """Add a correlation between two factors (-1 to +1).

        Positive values: factors move together.
        Negative values: factors move inversely.
        """
        self._graph.add_edge(factor_a, factor_b, "correlates_with", correlation)

    def add_complement(self, factor_a: str, factor_b: str) -> None:
        """Mark two factors as complementary (use together)."""
        self._graph.add_edge(factor_a, factor_b, "complements", 1.0)

    def add_substitute(self, factor_a: str, factor_b: str) -> None:
        """Mark two factors as substitutes (similar effect)."""
        self._graph.add_edge(factor_a, factor_b, "substitutes", 1.0)

    def get_correlated(self, factor_id: str, min_abs_corr: float = 0.3) -> List[Tuple[str, float]]:
        """Return factors correlated with factor_id above the threshold.

        Returns:
            List of (factor_id, correlation_value) tuples.
        """
        results = []
        for _, target, rel, weight in self._graph.edges:
            if _ == factor_id and rel == "correlates_with" and abs(weight) >= min_abs_corr:
                results.append((target, weight))
        return results

    def get_related(self, factor_id: str) -> List[Tuple[str, str]]:
        """Return all related factors with relation type."""
        return [(e[1], e[2]) for e in self._graph.edges if e[0] == factor_id]

    def get_all_correlations(self) -> List[Tuple[str, str, float]]:
        """Return all correlation edges as (factor_a, factor_b, correlation)."""
        return [(s, t, w) for s, t, r, w in self._graph.edges if r == "correlates_with"]

    def factor_count(self) -> int:
        return len(self._factor_definitions)

    def edge_count(self) -> int:
        return self._graph.edge_count

    def clear(self) -> None:
        self._graph = GraphBuilder()
        self._factor_definitions.clear()
