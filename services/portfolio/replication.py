"""
Portfolio replication models.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReplicationRecord:
    replication_id: str
    source_node: str
    target_node: str
    created_at: datetime
    status: str