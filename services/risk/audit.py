"""
Risk audit repository.
"""

from __future__ import annotations

from typing import List


class RiskAuditRepository:
    def __init__(self):
        self.events: List = []

    async def save(
        self,
        event,
    ):
        self.events.append(event)

    async def list_all(
        self,
    ):
        return self.events