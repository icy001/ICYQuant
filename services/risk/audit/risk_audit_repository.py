"""
Legacy flat risk audit repository, migrated into the ``audit`` package.

This class was previously defined in ``services/risk/audit.py`` (a flat
module).  Since Commit 41 Part 1.5 introduces the ``audit`` package for the
decision audit, the legacy repository moved here so that ``audit`` remains a
single importable unit.  Public API and behaviour are unchanged.
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


__all__ = [
    "RiskAuditRepository",
]
