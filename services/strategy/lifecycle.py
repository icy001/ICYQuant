"""
Strategy lifecycle.
"""

from __future__ import annotations

from enum import Enum


class StrategyLifecycle(str, Enum):
    CREATED = "CREATED"
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"