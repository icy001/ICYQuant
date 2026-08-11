"""
Decision Evidence — supporting evidence for a decision.

Records the actual data points that supported a decision:
  - Factor values (momentum, volatility, etc.)
  - Market conditions (trend, volume, etc.)
  - Risk metrics (VaR, stress, etc.)

Evidence makes decisions auditable and replayable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceItem:
    """A single piece of evidence supporting a decision."""

    key: str
    value: Any
    source: str = ""
    unit: str = ""
    description: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "unit": self.unit,
            "description": self.description,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceItem":
        return cls(
            key=data.get("key", ""),
            value=data.get("value"),
            source=data.get("source", ""),
            unit=data.get("unit", ""),
            description=data.get("description", ""),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class DecisionEvidence:
    """Collection of evidence items supporting a decision.

    Organized by category: factor, market, risk, portfolio, liquidity.
    """

    evidence_id: str
    decision_id: str = ""

    # Categorized evidence
    factor_evidence: List[EvidenceItem] = field(default_factory=list)
    market_evidence: List[EvidenceItem] = field(default_factory=list)
    risk_evidence: List[EvidenceItem] = field(default_factory=list)
    portfolio_evidence: List[EvidenceItem] = field(default_factory=list)
    liquidity_evidence: List[EvidenceItem] = field(default_factory=list)

    # All items (flat)
    all_items: List[EvidenceItem] = field(default_factory=list)

    timestamp: float = field(default_factory=time.time)

    def add_factor(self, key: str, value: Any, **kwargs) -> "DecisionEvidence":
        item = EvidenceItem(key=key, value=value, source="factor", **kwargs)
        self.factor_evidence.append(item)
        self.all_items.append(item)
        return self

    def add_market(self, key: str, value: Any, **kwargs) -> "DecisionEvidence":
        item = EvidenceItem(key=key, value=value, source="market", **kwargs)
        self.market_evidence.append(item)
        self.all_items.append(item)
        return self

    def add_risk(self, key: str, value: Any, **kwargs) -> "DecisionEvidence":
        item = EvidenceItem(key=key, value=value, source="risk", **kwargs)
        self.risk_evidence.append(item)
        self.all_items.append(item)
        return self

    def get(self, key: str) -> Optional[EvidenceItem]:
        """Find an item by key."""
        for item in self.all_items:
            if item.key == key:
                return item
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "decision_id": self.decision_id,
            "factor_evidence": [e.to_dict() for e in self.factor_evidence],
            "market_evidence": [e.to_dict() for e in self.market_evidence],
            "risk_evidence": [e.to_dict() for e in self.risk_evidence],
            "portfolio_evidence": [e.to_dict() for e in self.portfolio_evidence],
            "liquidity_evidence": [e.to_dict() for e in self.liquidity_evidence],
            "all_items": [e.to_dict() for e in self.all_items],
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionEvidence":
        def _parse_items(key: str) -> list:
            return [EvidenceItem.from_dict(i) for i in data.get(key, [])]

        return cls(
            evidence_id=data.get("evidence_id", ""),
            decision_id=data.get("decision_id", ""),
            factor_evidence=_parse_items("factor_evidence"),
            market_evidence=_parse_items("market_evidence"),
            risk_evidence=_parse_items("risk_evidence"),
            portfolio_evidence=_parse_items("portfolio_evidence"),
            liquidity_evidence=_parse_items("liquidity_evidence"),
            all_items=_parse_items("all_items"),
            timestamp=data.get("timestamp", time.time()),
        )
