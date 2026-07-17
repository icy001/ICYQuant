"""
Retry policy.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_retry: int = 3