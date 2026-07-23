"""
Decision trace system.
"""

from dataclasses import dataclass


@dataclass
class DecisionTrace:

    agent: str

    action: str

    reason: str

    confidence: float