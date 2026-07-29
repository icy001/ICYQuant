from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ThesisType(str, Enum):
    GROWTH = "GROWTH"
    VALUE = "VALUE"
    MOMENTUM = "MOMENTUM"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    MACRO = "MACRO"
    SECTOR_ROTATION = "SECTOR_ROTATION"
    RELATIVE_VALUE = "RELATIVE_VALUE"


class ThesisConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


@dataclass
class InvestmentThesis:
    thesis_id: str
    symbol: str
    thesis_type: ThesisType
    title: str
    why_buy: str
    why_now: str
    catalyst: str
    risks: List[str] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)
    expected_return: float = 0.0
    time_horizon: str = "6M"
    confidence: ThesisConfidence = ThesisConfidence.MEDIUM


@dataclass
class ThesisEvidence:
    fundamental: List[str] = field(default_factory=list)
    technical: List[str] = field(default_factory=list)
    macro: List[str] = field(default_factory=list)
    sentiment: List[str] = field(default_factory=list)


class InvestmentThesisGenerator:
    """Investment Thesis Generator - autonomously generates structured investment theses."""

    def __init__(self):
        self.thesis_count = 0
        self.theses: List[InvestmentThesis] = []

    def generate(self, opportunity):
        """Generate an investment thesis from an opportunity.

        Args:
            opportunity: The investment opportunity (str, dict, or InvestmentThesis).

        Returns:
            Dict containing the generated thesis.
        """
        if isinstance(opportunity, InvestmentThesis):
            return self._process_thesis(opportunity)
        if isinstance(opportunity, dict):
            return self._generate_from_dict(opportunity)
        return {"thesis": opportunity}

    def _process_thesis(self, thesis: InvestmentThesis) -> dict:
        self.thesis_count += 1
        self.theses.append(thesis)
        return {
            "thesis": {
                "thesis_id": thesis.thesis_id,
                "symbol": thesis.symbol,
                "type": thesis.thesis_type.value,
                "title": thesis.title,
                "why_buy": thesis.why_buy,
                "why_now": thesis.why_now,
                "catalyst": thesis.catalyst,
                "risks": thesis.risks,
                "exit_conditions": thesis.exit_conditions,
                "expected_return": round(thesis.expected_return, 2),
                "time_horizon": thesis.time_horizon,
                "confidence": thesis.confidence.value,
                "status": "GENERATED",
            }
        }

    def _generate_from_dict(self, data: dict) -> dict:
        title = data.get("title", "Generated Thesis")
        return {
            "thesis": {
                "title": title,
                "type": data.get("type", "GROWTH"),
                "symbol": data.get("symbol", "UNKNOWN"),
                "why_buy": data.get("why_buy", ""),
                "why_now": data.get("why_now", ""),
                "catalyst": data.get("catalyst", ""),
                "risks": data.get("risks", []),
                "exit_conditions": data.get("exit_conditions", []),
                "expected_return": data.get("expected_return", 0.0),
                "time_horizon": data.get("time_horizon", "6M"),
                "confidence": data.get("confidence", "MEDIUM"),
                "status": "GENERATED",
            }
        }

    def get_thesis_history(self) -> List[InvestmentThesis]:
        """Get all generated theses."""
        return list(self.theses)

    def get_thesis_by_symbol(self, symbol: str) -> List[InvestmentThesis]:
        """Get all theses for a specific symbol."""
        return [t for t in self.theses if t.symbol == symbol]

    def validate_thesis(self, thesis: InvestmentThesis) -> Dict[str, Any]:
        """Validate a thesis for completeness."""
        issues = []
        if not thesis.why_buy:
            issues.append("Missing: why buy")
        if not thesis.why_now:
            issues.append("Missing: why now")
        if not thesis.catalyst:
            issues.append("Missing: catalyst")
        if not thesis.risks:
            issues.append("Missing: risks")
        if not thesis.exit_conditions:
            issues.append("Missing: exit conditions")
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "score": max(0, 100 - len(issues) * 20),
        }
