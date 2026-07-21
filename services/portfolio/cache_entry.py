"""
Cache entry model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CacheEntry:

    cache_key: str

    created_at: datetime

    value: dict