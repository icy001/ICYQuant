"""
Parameter management service.
"""

from .snapshot import ParameterSnapshot


class ParameterService:
    def __init__(self):
        self._snapshots = {}

    def save(
        self,
        snapshot: ParameterSnapshot,
    ):
        self._snapshots[snapshot.version] = snapshot

    def load(
        self,
        version: str,
    ):
        return self._snapshots.get(version)