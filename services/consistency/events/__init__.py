"""Consistency domain events."""

from .consistency_failed import ConsistencyFailed
from .consistency_restored import ConsistencyRestored

__all__ = [
    "ConsistencyFailed",
    "ConsistencyRestored",
]
