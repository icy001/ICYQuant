"""
Research Permissions — Permissions for autonomous research operations.

Controls what research actions are allowed at different autonomy levels.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

RESEARCH_ACTIONS = [
    "explore_data",
    "generate_hypothesis",
    "run_experiment",
    "analyze_results",
    "publish_findings",
    "create_factor",
    "backtest_factor",
    "optimize_parameters",
]


class ResearchPermissions:
    """Permission checker for autonomous research domain."""

    def __init__(self, autonomy_engine=None):
        from .autonomy_engine import AutonomyEngine
        self._autonomy = autonomy_engine or AutonomyEngine()

    async def check(self, context) -> bool:
        """
        Check if research actions are permitted.

        Research is allowed at L1+ (the most permissive domain).
        """
        current = await self._autonomy.current_level()
        return current >= 1

    def allowed_actions(self, autonomy_level: int) -> list[str]:
        if autonomy_level >= 1:
            return RESEARCH_ACTIONS
        return []
