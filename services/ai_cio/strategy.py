"""CIO strategy planner for long-term investment strategy blueprints."""

from __future__ import annotations


class CIOStrategyPlanner:
    """Defines the CIO-level investment strategy blueprint.

    Sets the investment objective, risk target, time horizon, and
    high-level capital allocation direction.
    """

    def create_strategy(self, objective: str, risk_level: str) -> dict:
        """Create a CIO-level investment strategy.

        Args:
            objective: Investment objective (e.g. "growth", "income").
            risk_level: Risk tolerance (e.g. "moderate", "aggressive").

        Returns:
            Dict with ``objective`` and ``risk`` keys.
        """
        return {
            "objective": objective,
            "risk": risk_level,
        }
