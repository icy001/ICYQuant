"""
Research platform configuration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchPlatformConfig:

    platform_name: str

    version: str

    environment: str