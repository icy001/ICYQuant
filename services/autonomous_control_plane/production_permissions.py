"""
Production Permissions — Permissions for production autonomy.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ProductionPermissions:
    """Permission checker for production domain — highest restrictiveness."""

    def __init__(self, autonomy_engine=None):
        from .autonomy_engine import AutonomyEngine
        self._autonomy = autonomy_engine or AutonomyEngine()

    async def check(self, context) -> bool:
        """Full production autonomy requires L6."""
        current = await self._autonomy.current_level()
        return current >= 6
