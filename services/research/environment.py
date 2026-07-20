"""
Experiment environment snapshot.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentSnapshot:
    python_version: str
    platform: str
    timezone: str