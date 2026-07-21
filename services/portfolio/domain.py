"""
Portfolio domain.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioDomain:

    name: str

    version: str

    status: str