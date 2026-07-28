"""Decision Path Engine – builds the reasoning chain from macro → signal."""

from typing import Any, Dict, List, Optional


class DecisionPathEngine:
    """Constructs a causal reasoning path from upstream events to the final decision."""

    def build(self, nodes: List[str]) -> str:
        """Build a linear reasoning chain.

        Args:
            nodes: ordered reasoning steps, e.g. ["Fed Rate Cut", "Liquidity Improve", "BUY NVDA"].

        Returns:
            Arrow-joined reasoning path.
        """
        return " -> ".join(nodes)

    def build_with_weights(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a weighted reasoning path.

        Args:
            nodes: list of {"name": str, "weight": float} dicts.

        Returns:
            {"path": str, "total_weight": float}.
        """
        if not nodes:
            return {"path": "", "total_weight": 0.0}

        path = " -> ".join(f"{n['name']}({n['weight']:.2f})" for n in nodes)
        total_weight = sum(n["weight"] for n in nodes)
        return {"path": path, "total_weight": round(total_weight, 4)}

    def validate_path(self, nodes: List[str], expected_length: Optional[int] = None) -> bool:
        """Basic validation: path must have at least 2 nodes."""
        if expected_length is not None:
            return len(nodes) == expected_length
        return len(nodes) >= 2
