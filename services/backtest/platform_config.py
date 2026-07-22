"""
Backtesting platform configuration.
"""

from dataclasses import dataclass


@dataclass
class PlatformConfig:

    platform_name: str

    version: str

    environment: str