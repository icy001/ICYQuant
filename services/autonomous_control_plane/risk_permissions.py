"""
Risk Permissions — Permissions for autonomous risk optimization.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RiskPermissions:
    """Permission checker for risk domain."""

    def __init__(self, autonomy_engine=None):
        from .autonomy_engine import AutonomyEngine
        self._autonomy = autonomy_engine or AutonomyEngine()

    async def check(self, context) -> bool:
        """Risk optimization requires L3+."""
        current = await self._autonomy.current_level()
        return current >= 3
