"""
Feed metrics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeedMetrics:
    received: int = 0
    published: int = 0
    rejected: int = 0