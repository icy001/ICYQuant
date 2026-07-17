"""
Market service status.
"""

from __future__ import annotations

from enum import Enum


class MarketStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"