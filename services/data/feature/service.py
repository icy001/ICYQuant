"""
Feature service.
"""

from __future__ import annotations


class FeatureService:
    def __init__(
        self,
        offline,
        online,
    ):
        self.offline = offline
        self.online = online

    async def publish(
        self,
        feature,
    ):
        await self.offline.save(feature)
        await self.online.put(feature)