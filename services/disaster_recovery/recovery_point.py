from dataclasses import dataclass


@dataclass
class RecoveryPoint:
    point_id: str
    timestamp: int
    snapshot_id: str
