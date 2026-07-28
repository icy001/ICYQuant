from dataclasses import dataclass


@dataclass
class BackupSnapshot:
    snapshot_id: str
    source: str
    timestamp: int
    status: str
