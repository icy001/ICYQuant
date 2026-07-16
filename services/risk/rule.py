"""
Risk rule protocol.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .context import RiskContext
from .decision import RiskResult
from .model import RiskRequest


class RiskRule(Protocol):
    def evaluate(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Optional[RiskResult]:
        ...