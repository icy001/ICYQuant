"""
Risk rule protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .context import RiskContext
from .decision import RiskResult
from .model import RiskRequest


@dataclass
class RiskRule:
    rule_id: str
    name: str
    enabled: bool = True
    threshold: float = 0.0


class RiskRuleProtocol(Protocol):
    def evaluate(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Optional[RiskResult]:
        ...