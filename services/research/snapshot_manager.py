"""
Snapshot manager.
"""

from .manifest import ExperimentManifest


class SnapshotManager:
    def create(
        self,
        manifest: ExperimentManifest,
    ):
        return manifest