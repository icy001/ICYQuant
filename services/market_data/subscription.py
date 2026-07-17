"""
Subscription model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subscription:
    symbol: str
    subscriber_id: str