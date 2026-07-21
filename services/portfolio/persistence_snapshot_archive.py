"""
Snapshot archive.
"""


class SnapshotArchive:
    def archive(
        self,
        snapshot,
    ):
        return {
            "archived": True,
            "snapshot": snapshot,
        }