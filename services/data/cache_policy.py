"""
Cache policy.
"""

from enum import Enum


class CachePolicy(Enum):

    MEMORY_ONLY = "MEMORY_ONLY"

    REDIS_ONLY = "REDIS_ONLY"

    MEMORY_THEN_REDIS = "MEMORY_THEN_REDIS"

    WRITE_THROUGH = "WRITE_THROUGH"