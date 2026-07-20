"""
Reproducibility service.
"""

from .snapshot_manager import SnapshotManager


class ReproducibilityService:
    def __init__(
        self,
        manager,
        validator,
    ):
        self.manager = manager
        self.validator = validator

    def register(
        self,
        manifest,
    ):
        snapshot = self.manager.create(manifest)
        self.validator.validate(snapshot)
        return snapshot