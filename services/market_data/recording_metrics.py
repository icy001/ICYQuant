"""
Recording metrics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecordingMetrics:
    recorded: int = 0
    failed: int = 0