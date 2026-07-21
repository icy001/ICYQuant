"""
Version snapshot summary.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionSnapshot:
    latest_version: str
    total_versions: int