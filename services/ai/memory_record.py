"""
AI memory record.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryRecord:

    memory_id: str

    memory_type: str

    content: str

    created_at: datetime

    metadata: dict