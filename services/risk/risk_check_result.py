"""
Risk check result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskCheckResult:

    passed: bool

    reason: str