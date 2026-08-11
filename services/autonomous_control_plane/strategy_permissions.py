"""
Strategy Permissions — Permissions for autonomous strategy operations.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StrategyPermissions:
    """Permission checker for autonomous strategy domain."""

    def __init__(self, autonomy_engine=None):
        from .autonomy_engine import AutonomyEngine
        self._autonomy = autonomy_engine or AutonomyEngine()

    async def check(self, context) -> bool:
        """Strategy generation requires L2+."""
        current = await self._autonomy.current_level()
        return current >= 2
