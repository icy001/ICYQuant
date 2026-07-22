"""
Risk rule model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskRule:

    rule_id: str

    name: str

    enabled: bool

    parameters: dict