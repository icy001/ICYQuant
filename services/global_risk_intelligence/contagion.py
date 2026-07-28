"""Contagion Engine.

Models risk propagation across global financial networks.
Traces shock transmission paths and estimates spillover impact
when one market or asset class experiences stress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ContagionNode:
    """A node in the contagion network.

    Attributes:
        name: Asset/market node identifier.
        shock: Current shock magnitude [0, 1].
        resilience: Resistance to contagion [0, 1].
        connections: List of connected node names.
    """

    name: str = ""
    shock: float = 0.0
    resilience: float = 0.5
    connections: list[str] = field(default_factory=list)


@dataclass
class ContagionPath:
    """A traced contagion path through the network.

    Attributes:
        path: Ordered list of affected nodes.
        total_impact: Cumulative impact along the path.
        probability: Probability of this path materializing.
    """

    path: list[str] = field(default_factory=list)
    total_impact: float = 0.0
    probability: float = 0.0


@dataclass
class ContagionResult:
    """Complete contagion analysis result.

    Attributes:
        source: Originating shock source.
        affected_nodes: Nodes affected by contagion.
        propagation_paths: Traced propagation paths.
        systemic_impact: Estimated systemic impact [0, 1].
        cascade_probability: Probability of cascade.
    """

    source: str = ""
    affected_nodes: list[str] = field(default_factory=list)
    propagation_paths: list[ContagionPath] = field(default_factory=list)
    systemic_impact: float = 0.0
    cascade_probability: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_systemic_threat(self) -> bool:
        return self.systemic_impact >= 0.5


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ContagionEngine:
    """Models contagion propagation through global financial networks.

    Maintains a propagation graph where each node represents a
    market/asset class, connected by estimated contagion channels.

    Attributes:
        propagation_graph: Dict of source → [(target, strength, probability)]
        default_resilience: Baseline node resilience.
    """

    # Global contagion propagation graph
    # Format: source → [(target, contagion_strength, probability)]
    PROPAGATION_GRAPH: dict[str, list[tuple[str, float, float]]] = {
        "US Bond": [
            ("USD", 0.7, 0.6),
            ("NASDAQ", 0.5, 0.4),
            ("EM Debt", 0.6, 0.5),
        ],
        "USD": [
            ("NASDAQ", 0.3, 0.3),
            ("EM Debt", 0.8, 0.7),
            ("Commodities", 0.6, 0.5),
            ("EM FX", 0.85, 0.8),
        ],
        "NASDAQ": [
            ("AI Stocks", 0.9, 0.9),
            ("Semiconductor ETF", 0.85, 0.8),
            ("Growth Stocks", 0.8, 0.7),
            ("Crypto", 0.3, 0.2),
        ],
        "AI Stocks": [
            ("Semiconductor ETF", 0.95, 0.9),
            ("NASDAQ", 0.4, 0.3),
        ],
        "Semiconductor ETF": [
            ("AI Stocks", 0.9, 0.8),
            ("NASDAQ", 0.35, 0.3),
        ],
        "EM Debt": [
            ("EM FX", 0.85, 0.8),
            ("Commodities", 0.4, 0.3),
        ],
        "EM FX": [
            ("EM Debt", 0.75, 0.7),
            ("Commodities", 0.5, 0.4),
        ],
        "Commodities": [
            ("EM FX", 0.35, 0.3),
            ("Gold", 0.6, 0.5),
        ],
        "Gold": [
            ("USD", -0.5, 0.5),  # Negative contagion: Gold ↑ → USD ↓
            ("Safe Haven", 0.7, 0.6),
        ],
        "Crypto": [
            ("NASDAQ", 0.2, 0.15),
            ("Growth Stocks", 0.15, 0.1),
        ],
        "Credit Event": [
            ("US Bond", 0.6, 0.5),
            ("NASDAQ", 0.5, 0.4),
            ("EM Debt", 0.7, 0.6),
            ("USD", 0.4, 0.3),
        ],
    }

    def __init__(self, max_hops: int = 3) -> None:
        self.max_hops = max_hops

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyze(self, source: str,
                initial_shock: float = 0.5) -> ContagionResult:
        """Trace contagion propagation from a source node.

        Args:
            source: Source node name (must exist in propagation graph).
            initial_shock: Initial shock magnitude [0, 1].

        Returns:
            ContagionResult with propagation paths and systemic impact.
        """
        if source not in self.PROPAGATION_GRAPH:
            return ContagionResult(
                source=source,
                systemic_impact=0.0,
                cascade_probability=0.0,
            )

        affected: set[str] = {source}
        propagation_paths: list[ContagionPath] = []

        # BFS-style propagation with decay
        current_layer: list[tuple[str, float, float, list[str]]] = [
            (source, initial_shock, 1.0, [source])
        ]  # (node, shock, cumulative_prob, traced_path)
        next_layer: list[tuple[str, float, float, list[str]]] = []

        for hop in range(self.max_hops):
            for node, shock, cum_prob, path in current_layer:
                connections = self.PROPAGATION_GRAPH.get(node, [])
                for target, strength, prob in connections:
                    if target in affected:
                        continue
                    decay = 1.0 / (hop + 2)  # Shock decays with distance
                    propagated = shock * strength * decay
                    combined_prob = cum_prob * prob

                    if propagated >= 0.02:  # Minimum impact threshold
                        next_layer.append(
                            (target, propagated, combined_prob,
                             path + [target])
                        )
                        affected.add(target)

                        propagation_paths.append(ContagionPath(
                            path=path + [target],
                            total_impact=round(propagated, 4),
                            probability=round(combined_prob, 4),
                        ))

            current_layer = next_layer
            next_layer = []

        # Systemic impact: sum of all affected beyond source
        systemic = min(
            1.0,
            initial_shock * (1.0 + len(affected) * 0.1),
        )

        # Cascade probability: worst-case path probability
        cascade = max(
            (p.probability for p in propagation_paths), default=0.0,
        )

        return ContagionResult(
            source=source,
            affected_nodes=sorted(affected - {source}),
            propagation_paths=propagation_paths,
            systemic_impact=systemic,
            cascade_probability=cascade,
        )

    # ------------------------------------------------------------------
    # Multi-source analysis
    # ------------------------------------------------------------------

    def analyze_multi(self,
                      sources: dict[str, float]) -> dict[str, ContagionResult]:
        """Analyze contagion from multiple sources simultaneously.

        Args:
            sources: Dict of {source_name: shock_magnitude}.

        Returns:
            Dict of {source_name: ContagionResult}.
        """
        results: dict[str, ContagionResult] = {}
        for source, shock in sources.items():
            results[source] = self.analyze(source, shock)
        return results

    def most_threatened(self, sources: dict[str, float]) -> list[tuple[str, float]]:
        """Identify most threatened nodes across all sources.

        Returns:
            Sorted list of (node_name, aggregate_impact).
        """
        threat_map: dict[str, float] = {}
        for source, shock in sources.items():
            result = self.analyze(source, shock)
            for path in result.propagation_paths:
                for node in path.path[1:]:  # Skip source
                    threat_map[node] = threat_map.get(node, 0.0) + path.total_impact
        return sorted(threat_map.items(), key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_exposure(self, node: str) -> float:
        """Get aggregate exposure of a node (sum of incoming strengths)."""
        total = 0.0
        for connections in self.PROPAGATION_GRAPH.values():
            for target, strength, _ in connections:
                if target == node:
                    total += strength
        return min(1.0, total)
