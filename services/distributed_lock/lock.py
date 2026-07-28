from dataclasses import dataclass


@dataclass
class DistributedLock:
    lock_id: str
    resource: str
    owner: str
    status: str
    timestamp: int
