"""
Risk domain model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDomain:

    domain_id: str

    name: str

    version: str

    status: str