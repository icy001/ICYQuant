"""
Execution Permissions — Permissions for autonomous execution.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ExecutionPermissions:
    """Permission checker for execution domain."""

    def __init__(self, autonomy_engine=None):
        from .autonomy_engine import AutonomyEngine
        self._autonomy = autonomy_engine or AutonomyEngine()

    async def check(self, context) -> bool:
        """Live order proposals require L4+, autonomous execution requires L5+."""
        current = await self._autonomy.current_level()
        action = getattr(context, "action", "")

        if action == "autonomous_execution":
            return current >= 5
        if action == "propose_order":
            return current >= 4
        return current >= 4
