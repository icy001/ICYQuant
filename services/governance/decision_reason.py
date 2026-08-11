"""
Decision Reason — captures WHY a decision was made, not just WHAT.

Reason types categorize the driving factor behind each decision:
  SIGNAL, FACTOR, RISK, PORTFOLIO, POLICY, MARKET, LIQUIDITY,
  HUMAN_OVERRIDE, EMERGENCY
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class ReasonType(Enum):
    """Categories for decision reasons."""

    SIGNAL = auto()           # Signal-driven (momentum, trend, etc.)
    FACTOR = auto()           # Factor model output
    RISK = auto()             # Risk management driven
    PORTFOLIO = auto()        # Portfolio optimization driven
    POLICY = auto()           # Policy compliance driven
    MARKET = auto()           # Market condition driven
    LIQUIDITY = auto()        # Liquidity management driven
    HUMAN_OVERRIDE = auto()   # Human intervention
    EMERGENCY = auto()        # Emergency action
    REBALANCE = auto()        # Periodic rebalancing


@dataclass
class DecisionReason:
    """A single reason explaining why a decision was made.

    Each decision can have multiple reasons (primary + supporting).
    """

    reason_id: str
    reason_type: ReasonType
    reason_text: str
    confidence: float = 0.0  # 0.0 - 1.0

    # Source attribution
    source: str = ""         # e.g. "momentum-v7", "risk-controller"
    source_version: str = ""

    # Supporting details
    details: Dict[str, Any] = field(default_factory=dict)

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason_id": self.reason_id,
            "reason_type": self.reason_type.name,
            "reason_text": self.reason_text,
            "confidence": self.confidence,
            "source": self.source,
            "source_version": self.source_version,
            "details": self.details,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionReason":
        reason_type = data.get("reason_type", "SIGNAL")
        if isinstance(reason_type, str):
            reason_type = ReasonType[reason_type]
        return cls(
            reason_id=data.get("reason_id", ""),
            reason_type=reason_type,
            reason_text=data.get("reason_text", ""),
            confidence=data.get("confidence", 0.0),
            source=data.get("source", ""),
            source_version=data.get("source_version", ""),
            details=data.get("details", {}),
            timestamp=data.get("timestamp", time.time()),
        )
